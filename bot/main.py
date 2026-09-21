import asyncio, hashlib, hmac, json, os, secrets, logging
from io import BytesIO
from datetime import datetime
from aiohttp import web
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    Message,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from cryptography.fernet import Fernet
from redis.asyncio import Redis

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SECRET = os.environ["BOT_INTERNAL_SECRET"]
APP = os.getenv("APP_URL", "http://localhost:3000")
API = os.getenv("API_INTERNAL_URL", "http://backend:8000")
redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
cipher = Fernet(os.environ["ENCRYPTION_KEY"].encode())
storage = RedisStorage(
    redis,
    state_ttl=3600,
    data_ttl=3600,
    json_dumps=lambda x: cipher.encrypt(json.dumps(x).encode()).decode(),
    json_loads=lambda x: json.loads(cipher.decrypt(x.encode())),
)
bot = Bot(TOKEN)
dp = Dispatcher(storage=storage)


class Flow(StatesGroup):
    wizard = State()
    record = State()
    support = State()


def keyboard(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=c) for t, c in row]
            for row in rows
        ]
    )


def menu():
    rows = [
        [InlineKeyboardButton(text="💬 Спросить Neyrix Mama", callback_data="chat")],
        [InlineKeyboardButton(text="➕ Добавить данные", callback_data="data")],
        [
            InlineKeyboardButton(text="🤰 Моя беременность", callback_data="profile"),
            InlineKeyboardButton(text="📊 Динамика", callback_data="dynamics"),
        ],
        [
            InlineKeyboardButton(
                text="🌐 Открыть приложение", web_app=WebAppInfo(url=APP + "/app")
            )
        ],
        [InlineKeyboardButton(text="🆘 Помощь", callback_data="support")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def api(user_id, path, method="GET", data=None, files=None):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            API + "/api" + path,
            headers={"X-Bot-Secret": SECRET, "X-Telegram-Id": str(user_id)},
            json=data if files is None else None,
            files=files,
        )
        result = response.json()
        if response.status_code >= 400:
            raise ValueError(
                result.get(
                    "detail", "Не получилось выполнить действие. Попробуйте позже."
                )
            )
        return result


async def safe_answer(message, text, markup=None):
    for i in range(0, len(text), 3900):
        await message.answer(
            text[i : i + 3900], reply_markup=markup if i + 3900 >= len(text) else None
        )


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    arg = (message.text or "").split(maxsplit=1)
    if len(arg) > 1 and arg[1].startswith("link_"):
        token = arg[1][5:]
        if len(token) != 32:
            await message.answer("Ссылка некорректна. Создайте новую в Web.")
            return
        await message.answer(
            f"Подключить этот Telegram-аккаунт (ID {message.from_user.id}) к профилю в Web? Продолжайте, только если вы сами создали ссылку.",
            reply_markup=keyboard(
                [[("Подтвердить", "link:" + token)], [("Отмена", "cancel")]]
            ),
        )
        return
    try:
        result = await api(
            message.from_user.id,
            "/internal/telegram/register",
            "POST",
            {
                "id": message.from_user.id,
                "name": message.from_user.first_name,
                "username": message.from_user.username,
            },
        )
        if not result["consented"]:
            await message.answer(
                "Добро пожаловать в Neyrix Mama 💛\n\nЯ помогу хранить данные о беременности, разбираться в анализах и УЗИ, следить за динамикой. Для начала настроим профиль.\n\nПеред продолжением ознакомьтесь с условиями обработки персональных данных и сведений о здоровье: "
                + APP
                + "/privacy",
                reply_markup=keyboard([[("Согласна, начать", "consent")]]),
            )
        else:
            await message.answer(
                "Neyrix Mama рядом. Что хотите сделать?", reply_markup=menu()
            )
    except Exception as exc:
        await message.answer(
            str(exc) if isinstance(exc, ValueError) else "Сервис временно недоступен."
        )


@dp.callback_query(F.data.startswith("link:"))
async def link(cb: CallbackQuery):
    await cb.answer()
    try:
        result = await api(
            cb.from_user.id,
            "/internal/telegram/link",
            "POST",
            {"token": cb.data[5:], "telegram_id": cb.from_user.id},
        )
        await cb.message.answer(result["message"])
    except ValueError as exc:
        await cb.message.answer(str(exc))


@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await cb.message.answer("Действие отменено.", reply_markup=menu())


STEPS = [
    ("name", "Как к вам обращаться?", None),
    ("age", "Сколько вам лет?", "number"),
    ("height", "Ваш рост в сантиметрах?", "number"),
    ("pre_weight", "Вес до беременности в кг?", "number"),
    ("current_weight", "Текущий вес в кг?", "number"),
    ("lmp", "Первый день последней менструации? Введите ГГГГ-ММ-ДД.", "date"),
    ("due_date", "ПДР, если её уже определили? ГГГГ-ММ-ДД.", "date"),
    (
        "first_pregnancy",
        "Это первая беременность?",
        ["Да", "Нет", "Предпочитаю не отвечать"],
    ),
    (
        "history",
        "Если хотите, расскажите о предыдущих беременностях, родах и операциях.",
        None,
    ),
    ("chronic", "Какие хронические заболевания и ограничения важно учитывать?", None),
    ("allergies", "Есть ли аллергии?", None),
    (
        "blood_group",
        "Группа крови?",
        ["O (I)", "A (II)", "B (III)", "AB (IV)", "Не знаю"],
    ),
    ("rh", "Резус-фактор?", ["Положительный", "Отрицательный", "Не знаю"]),
    (
        "activity",
        "Ваша обычная физическая активность?",
        [
            "Не занималась",
            "Лёгкая активность",
            "Регулярные тренировки",
            "Силовые тренировки",
            "Кардио / бег",
            "Йога / пилатес",
        ],
    ),
    ("frequency", "Сколько тренировок в неделю?", "number"),
    ("training_history", "Ваш опыт тренировок и ограничения?", None),
    (
        "medications",
        "Какие лекарства назначил врач? Укажите название и дозу, если знаете.",
        None,
    ),
    ("supplements", "Какие витамины и добавки принимаете?", None),
    ("lifestyle", "Особенности питания и образа жизни. Можно пропустить.", None),
]


async def ask(message, state):
    data = await state.get_data()
    index = data.get("step", 0)
    if index >= len(STEPS):
        await state.clear()
        await message.answer(
            "Всё готово 💛\nNeyrix Mama настроена под вашу беременность. Данные можно изменить в любой момент.",
            reply_markup=menu(),
        )
        return
    key, prompt, kind = STEPS[index]
    rows = []
    if isinstance(kind, list):
        rows = [[(text, "answer:" + str(i))] for i, text in enumerate(kind)]
    rows.append([("Пропустить", "skip")])
    await message.answer(
        f"Шаг {index + 1} из {len(STEPS)}\n\n{prompt}", reply_markup=keyboard(rows)
    )


@dp.callback_query(F.data.in_({"consent", "edit-profile"}))
async def consent(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    try:
        if cb.data == "consent":
            cfg = await api(cb.from_user.id, "/public-config")
            await api(
                cb.from_user.id,
                "/consent",
                "POST",
                {"accepted": True, "version": cfg["privacy_version"]},
            )
        me = await api(cb.from_user.id, "/me")
        await state.set_state(Flow.wizard)
        await state.set_data({"step": 0, "profile": me["profile"]})
        await ask(cb.message, state)
    except ValueError as exc:
        await cb.message.answer(str(exc))


async def wizard_value(message, user_id, state, value=None):
    data = await state.get_data()
    index = data["step"]
    key, prompt, kind = STEPS[index]
    profile = data.get("profile", {})
    if value is not None:
        try:
            if kind == "number":
                value = float(value.replace(",", "."))
                if key in ("age", "frequency"):
                    value = int(value)
            if kind == "date":
                value = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except (ValueError, TypeError):
            await message.answer(
                "Не удалось прочитать значение. Проверьте формат и попробуйте ещё раз."
            )
            return
        profile = {**profile, key: value}
    try:
        profile["completed"] = index == len(STEPS) - 1
        result = await api(user_id, "/profile", "PUT", profile)
        await state.update_data(step=index + 1, profile=result["profile"])
        await ask(message, state)
    except ValueError as exc:
        await message.answer(str(exc))


@dp.callback_query(Flow.wizard, F.data.startswith("answer:"))
async def answer_choice(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    kind = STEPS[data["step"]][2]
    await wizard_value(
        cb.message, cb.from_user.id, state, kind[int(cb.data.split(":")[1])]
    )


@dp.callback_query(Flow.wizard, F.data == "skip")
async def skip(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await wizard_value(cb.message, cb.from_user.id, state)


@dp.message(Flow.wizard, F.text)
async def answer_text(message: Message, state: FSMContext):
    await wizard_value(message, message.from_user.id, state, message.text)


@dp.callback_query(F.data.in_({"profile", "dynamics", "chat", "data", "support"}))
async def navigation(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    try:
        if cb.data == "profile":
            me = await api(cb.from_user.id, "/me")
            g = me.get("gestation")
            profile = me["profile"]
            await cb.message.answer(
                f"Моя беременность\n\n{profile.get('name', '')}\n"
                + (
                    f"Срок: {g['weeks']} недель {g['days']} дней\nПДР: {g['due_date']}"
                    if g
                    else "Срок пока не указан."
                ),
                reply_markup=keyboard([[("Изменить профиль", "edit-profile")]]),
            )
        elif cb.data == "dynamics":
            rows = await api(cb.from_user.id, "/records")
            values = [
                f"{r.get('title') or r['kind']}: {r.get('value') or ''} {r.get('unit', '')} — {r['recorded_at'][:10]}"
                for r in rows[:10]
            ]
            await cb.message.answer(
                "Последние данные\n\n"
                + ("\n".join(values) or "Добавьте первое измерение."),
                reply_markup=menu(),
            )
        elif cb.data == "data":
            await cb.message.answer(
                "Отправьте фото, PDF, DOCX или TXT до 15 МБ. Или добавьте запись:",
                reply_markup=keyboard(
                    [
                        [
                            ("⚖️ Вес", "record:weight"),
                            ("❤️ Давление", "record:blood_pressure"),
                        ],
                        [
                            ("💊 Лекарство", "record:medication"),
                            ("🤰 Симптом", "record:symptom"),
                        ],
                        [
                            ("🏋️ Тренировка", "record:activity"),
                            ("📝 Заметка", "record:note"),
                        ],
                    ]
                ),
            )
        elif cb.data == "chat":
            await cb.message.answer(
                "Напишите, что вас волнует. Я учту вашу беременность и подтверждённые показатели."
            )
        elif cb.data == "support":
            await state.set_state(Flow.support)
            await cb.message.answer(
                "Опишите проблему одним сообщением. Это техническая поддержка, а не медицинская консультация."
            )
    except ValueError as exc:
        await cb.message.answer(str(exc))


@dp.callback_query(F.data.startswith("record:"))
async def record_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    kind = cb.data.split(":")[1]
    await state.set_state(Flow.record)
    await state.update_data(kind=kind)
    await cb.message.answer(
        "Введите вес в кг."
        if kind == "weight"
        else "Введите давление в формате 120/80."
        if kind == "blood_pressure"
        else "Напишите, что сохранить."
    )


@dp.message(Flow.record, F.text)
async def save_record(message: Message, state: FSMContext):
    kind = (await state.get_data())["kind"]
    data = {
        "kind": kind,
        "recorded_at": datetime.now().isoformat(),
        "title": "",
        "notes": "",
    }
    try:
        if kind == "weight":
            data.update(
                value=float(message.text.replace(",", ".")), unit="кг", title="Вес"
            )
        elif kind == "blood_pressure":
            a, b = message.text.split("/")
            data.update(
                value=float(a), secondary=float(b), unit="мм рт. ст.", title="Давление"
            )
        else:
            data.update(notes=message.text, title=message.text[:60])
        await api(message.from_user.id, "/records", "POST", data)
        await state.clear()
        await message.answer("Запись сохранена.", reply_markup=menu())
    except (ValueError, TypeError) as exc:
        await message.answer("Проверьте значение. " + str(exc))


@dp.message(Flow.support, F.text)
async def support(message: Message, state: FSMContext):
    try:
        result = await api(
            message.from_user.id,
            "/support",
            "POST",
            {"category": "Другое", "text": message.text},
        )
        await state.clear()
        await message.answer(
            "Обращение создано: "
            + result["id"][:8]
            + ". Ответ появится в разделе помощи приложения.",
            reply_markup=menu(),
        )
    except ValueError as exc:
        await message.answer(str(exc))


async def wait_task(user_id, id):
    for _ in range(90):
        result = await api(user_id, "/tasks/" + id)
        if result["status"] == "done":
            return result["result"]
        if result["status"] == "failed":
            raise ValueError(
                result["result"].get("error", "Не получилось обработать запрос.")
            )
        await asyncio.sleep(3)
    raise ValueError("Обработка продолжается. Результат появится в приложении.")


@dp.message(F.photo | F.document)
async def document(message: Message):
    file = message.photo[-1] if message.photo else message.document
    name = (
        "photo.jpg" if message.photo else message.document.file_name or "document.pdf"
    )
    if file.file_size and file.file_size > 15 * 1024 * 1024:
        await message.answer("Файл больше 15 МБ. Выберите файл меньшего размера.")
        return
    try:
        content = BytesIO()
        await bot.download(file, destination=content)
        result = await api(
            message.from_user.id,
            "/documents",
            "POST",
            files={"file": (name, content.getvalue())},
        )
        await message.answer("Документ получен. Обрабатываю его…")
        await wait_task(message.from_user.id, result["task_id"])
        docs = await api(message.from_user.id, "/documents")
        doc = next(d for d in docs if d["id"] == result["id"])
        ex = doc["extraction"]
        summary = "\n".join(
            f"{v.get('title')}: {v.get('value')} {v.get('unit', '')}"
            for v in ex.get("values", [])[:25]
        )
        await safe_answer(
            message,
            "Проверьте данные по оригиналу. Распознавание может ошибаться.\n\n"
            + summary
            + "\n\nДата: "
            + str(ex.get("date") or "не определена"),
            keyboard(
                [
                    [("Сохранить", "confirm:" + doc["id"])],
                    [("Исправить в приложении", "open-review")],
                    [("Не сохранять показатели", "cancel")],
                ]
            ),
        )
    except Exception as exc:
        await message.answer(
            str(exc)
            if isinstance(exc, ValueError)
            else "Не получилось загрузить файл. Попробуйте через приложение."
        )


@dp.callback_query(F.data == "open-review")
async def open_review(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "Откройте «Мои данные» и выберите документ, чтобы проверить или исправить значения.",
        reply_markup=menu(),
    )


@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_document(cb: CallbackQuery):
    await cb.answer()
    try:
        docs = await api(cb.from_user.id, "/documents")
        doc = next(d for d in docs if d["id"] == cb.data.split(":")[1])
        ex = doc["extraction"]
        if not ex.get("date") or any(
            v.get("value") is None for v in ex.get("values", [])
        ):
            await cb.message.answer(
                "Не все данные распознаны. Укажите дату и проверьте значения в приложении.",
                reply_markup=menu(),
            )
            return
        values = [
            {
                "kind": v.get("kind")
                if v.get("kind") in ("lab", "ultrasound")
                else "lab",
                "title": v.get("title", ""),
                "value": v.get("value"),
                "unit": v.get("unit", ""),
                "reference": v.get("reference", ""),
                "recorded_at": ex["date"] + "T12:00:00",
            }
            for v in ex.get("values", [])
        ]
        await api(
            cb.from_user.id,
            "/documents/" + doc["id"] + "/confirm",
            "POST",
            {"records": values},
        )
        await cb.message.answer(
            "Данные сохранены. Срок беременности не изменён; предложение можно отдельно проверить в приложении.",
            reply_markup=menu(),
        )
    except Exception as exc:
        await cb.message.answer(
            str(exc)
            if isinstance(exc, ValueError)
            else "Не получилось подтвердить документ."
        )


@dp.message(F.text)
async def chat(message: Message):
    try:
        task = await api(message.from_user.id, "/chat", "POST", {"text": message.text})
        await message.answer("Обдумываю ваш вопрос…")
        result = await wait_task(message.from_user.id, task["task_id"])
        await safe_answer(message, result["text"], menu())
    except Exception as exc:
        await message.answer(
            str(exc)
            if isinstance(exc, ValueError)
            else "Сервис временно недоступен. Попробуйте позже."
        )


async def notify(request):
    if not hmac.compare_digest(request.headers.get("X-Bot-Secret", ""), SECRET):
        raise web.HTTPUnauthorized()
    data = await request.json()
    await bot.send_message(
        chat_id=data["chat_id"], text=data["text"], reply_markup=menu()
    )
    return web.json_response({"ok": True})


async def health(request):
    return web.json_response({"status": "ok"})


async def polling():
    key = "polling:" + hashlib.sha256(TOKEN.encode()).hexdigest()
    owner = secrets.token_hex(16)
    if not await redis.set(key, owner, nx=True, ex=60):
        raise RuntimeError("Polling already running for this token")

    async def renew():
        while True:
            await asyncio.sleep(20)
            if not await redis.eval(
                "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('expire',KEYS[1],60) else return 0 end",
                1,
                key,
                owner,
            ):
                await dp.stop_polling()
                return

    task = asyncio.create_task(renew())
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await redis.eval(
            "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
            1,
            key,
            owner,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if os.getenv("BOT_MODE", "webhook") == "polling":
        asyncio.run(polling())
    else:
        app = web.Application(client_max_size=20 * 1024 * 1024)
        webhook_secret = os.environ["TELEGRAM_WEBHOOK_SECRET"]
        if len(webhook_secret) < 32:
            raise RuntimeError("Webhook secret must be at least 32 characters")
        SimpleRequestHandler(
            dispatcher=dp, bot=bot, secret_token=webhook_secret
        ).register(app, path="/telegram/webhook")
        app.router.add_post("/internal/notify", notify)
        app.router.add_get("/health", health)
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=8001, access_log=None)
