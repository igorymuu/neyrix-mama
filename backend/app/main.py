import hmac, secrets, json
from pathlib import Path
from datetime import timedelta
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    File,
    Body,
)
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, delete, func, text
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import get_db
from .models import *
from .security import *
from .services import *
from .schemas import *
from . import storage
from .payments import provider, reconcile, add_months
from .knowledge import weekly_summary

app = FastAPI(
    title="Neyrix Mama API",
    docs_url=None if settings().production else "/api/docs",
    openapi_url=None if settings().production else "/api/openapi.json",
)


@app.middleware("http")
async def protect(request: Request, call_next):
    path = request.url.path
    internal = request.headers.get("X-Bot-Secret", "")
    is_internal = bool(internal) and hmac.compare_digest(
        internal, settings().bot_internal_secret
    )
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and path != "/api/payments/webhook"
        and not is_internal
    ):
        if request.headers.get("origin") != settings().app_url:
            return JSONResponse(
                {"detail": "Не удалось проверить источник запроса. Обновите страницу."},
                403,
            )
    try:
        size = int(request.headers.get("content-length", "0"))
    except ValueError:
        return JSONResponse({"detail": "Некорректный запрос."}, 400)
    if size > (settings().max_upload_mb + 1) * 1024 * 1024:
        return JSONResponse({"detail": "Файл слишком большой."}, 413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    return JSONResponse(
        {
            "detail": "Проверьте заполненные поля.",
            "fields": [
                {"field": ".".join(map(str, x["loc"][1:])), "message": x["msg"]}
                for x in exc.errors()
            ],
        },
        422,
    )


@app.exception_handler(Exception)
async def unexpected(request, exc):
    diagnostic_id = secrets.token_hex(8)
    import logging

    logging.getLogger("mama").error(
        "Unhandled %s diagnostic=%s", type(exc).__name__, diagnostic_id
    )
    return JSONResponse(
        {
            "detail": "Что-то пошло не так. Попробуйте ещё раз.",
            "diagnostic_id": diagnostic_id,
        },
        500,
    )


@app.get("/api/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    try:
        redis_client().ping()
    except Exception:
        raise HTTPException(503, "Очередь недоступна")
    return {"status": "ok"}


@app.get("/api/public-config")
def public_config(db=Depends(get_db)):
    c = config(db)
    return {
        "google_client_id": settings().google_client_id,
        "bot_username": settings().telegram_bot_username,
        "price": c["price"],
        "trial_days": c["trial_days"],
        "privacy_version": settings().privacy_version,
    }


@app.get("/api/auth/challenge")
def challenge(response: Response):
    nonce = secrets.token_urlsafe(32)
    response.set_cookie(
        "mama_nonce",
        nonce,
        httponly=True,
        secure=settings().production,
        samesite="lax",
        max_age=300,
        path="/",
    )
    return {"nonce": nonce}


@app.post("/api/auth/google")
def google_login(
    request: Request, response: Response, body: dict = Body(...), db=Depends(get_db)
):
    rate_limit("google:" + request.client.host, 15)
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request as GoogleRequest

    try:
        claims = id_token.verify_oauth2_token(
            body.get("credential", ""), GoogleRequest(), settings().google_client_id
        )
        if (
            not claims.get("email_verified")
            or not request.cookies.get("mama_nonce")
            or not hmac.compare_digest(
                claims.get("nonce", ""), request.cookies["mama_nonce"]
            )
        ):
            raise ValueError()
    except Exception:
        raise HTTPException(
            401, "Не получилось войти через Google. Попробуйте ещё раз."
        )
    user = new_user(
        db,
        "google",
        claims["sub"],
        {"email": claims.get("email"), "name": claims.get("name")},
    )
    if claims["sub"] in settings().admin_google_subjects.split(","):
        user.role = "admin"
    response.delete_cookie("mama_nonce")
    set_session(db, response, user)
    return {"ok": True}


@app.post("/api/auth/telegram")
def telegram_login(response: Response, body: dict = Body(...), db=Depends(get_db)):
    data = verify_telegram(body.get("init_data", ""))
    rate_limit("tg-auth:" + str(data["id"]), 15)
    user = new_user(
        db,
        "telegram",
        str(data["id"]),
        {"name": data.get("first_name"), "username": data.get("username")},
    )
    set_session(db, response, user)
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db=Depends(get_db)):
    db.execute(
        delete(Session).where(
            Session.token_hash == digest(request.cookies.get("mama_session", ""))
        )
    )
    db.commit()
    response.delete_cookie("mama_session")
    return {"ok": True}


@app.post("/api/internal/telegram/register", dependencies=[Depends(internal_only)])
def register_telegram(body: dict = Body(...), db=Depends(get_db)):
    subject = str(body.get("id", ""))
    if not subject.isdigit():
        raise HTTPException(422, "Некорректный аккаунт")
    user = new_user(
        db,
        "telegram",
        subject,
        {
            "name": str(body.get("name", ""))[:100],
            "username": str(body.get("username", ""))[:100],
        },
    )
    db.commit()
    return {"consented": bool(user.consent_at), "profile": user.profile}


@app.get("/api/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    identities = list(db.scalars(select(Identity).where(Identity.user_id == user.id)))
    return {
        "id": user.id,
        "profile": user.profile,
        "gestation": gestation(user.profile),
        "week_summary": weekly_summary(db, user.profile),
        "consented": bool(user.consent_at),
        "preferences": user.preferences,
        "identities": [{"provider": i.provider, **i.info} for i in identities],
        "subscription": usage(db, user.id),
    }


@app.post("/api/consent")
def consent(body: dict = Body(...), user=Depends(current_user), db=Depends(get_db)):
    if (
        body.get("accepted") is not True
        or body.get("version") != settings().privacy_version
    ):
        raise HTTPException(422, "Подтвердите согласие с актуальными условиями.")
    user.consent_at = now()
    user.consent_version = settings().privacy_version
    audit(db, user.id, "consent.accept")
    db.commit()
    return {"ok": True}


@app.put("/api/profile")
def update_profile(body: Profile, user=Depends(consent_user), db=Depends(get_db)):
    save_profile(db, user, body)
    db.commit()
    return {"profile": user.profile, "gestation": gestation(user.profile)}


@app.get("/api/profile/history")
def profile_history(user=Depends(consent_user), db=Depends(get_db)):
    return [
        {"id": r.id, "created_at": r.created_at, "data": r.data}
        for r in db.scalars(
            select(ProfileChange)
            .where(ProfileChange.user_id == user.id)
            .order_by(ProfileChange.created_at.desc())
            .limit(100)
        )
    ]


@app.put("/api/preferences")
def preferences(body: dict = Body(...), user=Depends(current_user), db=Depends(get_db)):
    user.preferences = {k: body.get(k) is True for k in ("reminders", "weekly")}
    db.commit()
    return user.preferences


@app.post("/api/link/telegram")
def create_link(user=Depends(current_user), db=Depends(get_db)):
    token = secrets.token_urlsafe(24)
    db.execute(delete(LinkToken).where(LinkToken.user_id == user.id))
    db.add(
        LinkToken(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=now() + timedelta(minutes=10),
        )
    )
    db.commit()
    return {
        "url": f"https://t.me/{settings().telegram_bot_username}?start=link_{token}"
    }


@app.post("/api/internal/telegram/link", dependencies=[Depends(internal_only)])
def claim_link(body: dict = Body(...), db=Depends(get_db)):
    link = db.scalar(
        select(LinkToken)
        .where(LinkToken.token_hash == digest(body.get("token", "")))
        .with_for_update()
    )
    subject = str(body.get("telegram_id", ""))
    if not link or link.expires_at < now() or not subject.isdigit():
        raise HTTPException(400, "Ссылка устарела. Создайте новую в приложении.")
    existing = db.scalar(
        select(Identity).where(
            Identity.provider == "telegram", Identity.subject == subject
        )
    )
    attached = db.scalar(
        select(Identity).where(
            Identity.user_id == link.user_id, Identity.provider == "telegram"
        )
    )
    if (existing and existing.user_id != link.user_id) or (
        attached and attached.subject != subject
    ):
        raise HTTPException(
            409,
            "У этих аккаунтов уже есть отдельные данные. Автоматическое объединение запрещено. Обратитесь в поддержку.",
        )
    if link.telegram_subject and link.telegram_subject != subject:
        raise HTTPException(409, "Ссылка уже использована другим аккаунтом.")
    link.telegram_subject = subject
    db.commit()
    return {
        "ok": True,
        "message": "Теперь вернитесь в Web и подтвердите подключение этого Telegram-аккаунта.",
    }


@app.get("/api/link/telegram")
def pending_link(user=Depends(current_user), db=Depends(get_db)):
    link = db.scalar(
        select(LinkToken).where(
            LinkToken.user_id == user.id, LinkToken.expires_at > now()
        )
    )
    return {"telegram_id": link.telegram_subject if link else None}


@app.post("/api/link/telegram/confirm")
def confirm_link(
    body: dict = Body(...), user=Depends(current_user), db=Depends(get_db)
):
    link = db.scalar(
        select(LinkToken)
        .where(LinkToken.user_id == user.id, LinkToken.expires_at > now())
        .with_for_update()
    )
    if (
        not link
        or not link.telegram_subject
        or body.get("telegram_id") != link.telegram_subject
    ):
        raise HTTPException(400, "Подключение не найдено. Начните заново.")
    existing = db.scalar(
        select(Identity).where(
            Identity.provider == "telegram", Identity.subject == link.telegram_subject
        )
    )
    attached = db.scalar(
        select(Identity).where(
            Identity.provider == "telegram", Identity.user_id == user.id
        )
    )
    if (existing and existing.user_id != user.id) or (
        attached and attached.subject != link.telegram_subject
    ):
        raise HTTPException(409, "Аккаунт уже подключён к другому профилю.")
    if not existing:
        db.add(
            Identity(
                user_id=user.id,
                provider="telegram",
                subject=link.telegram_subject,
                info={},
            )
        )
    db.delete(link)
    audit(db, user.id, "identity.link.telegram")
    db.commit()
    return {"ok": True}


@app.get("/api/records")
def records(user=Depends(consent_user), db=Depends(get_db)):
    return [
        serialize_record(r)
        for r in db.scalars(
            select(Record)
            .where(Record.user_id == user.id)
            .order_by(Record.recorded_at.desc())
            .limit(1000)
        )
    ]


@app.post("/api/records")
def create_record(body: RecordInput, user=Depends(consent_user), db=Depends(get_db)):
    row = add_record(db, user, body)
    db.commit()
    return serialize_record(row)


@app.get("/api/documents")
def documents(user=Depends(consent_user), db=Depends(get_db)):
    return [
        serialize_doc(d)
        for d in db.scalars(
            select(MedicalDocument)
            .where(MedicalDocument.user_id == user.id)
            .order_by(MedicalDocument.created_at.desc())
            .limit(300)
        )
    ]


def owned(db, model, id, user):
    row = db.get(model, id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Не найдено")
    return row


@app.post("/api/documents")
async def upload(
    file: UploadFile = File(...), user=Depends(consent_user), db=Depends(get_db)
):
    rate_limit("upload:" + user.id, 20, 3600)
    data = await file.read(settings().max_upload_mb * 1024 * 1024 + 1)
    name = Path(file.filename or "document").name[:180]
    mime = storage.validate(data, name)
    doc = MedicalDocument(
        user_id=user.id,
        storage_key=user.id + "/" + uid(),
        details={"name": name, "mime": mime, "size": len(data)},
    )
    storage.save(doc.storage_key, data)
    db.add(doc)
    db.commit()
    try:
        task = submit(db, user.id, "document", {"document_id": doc.id})
    except HTTPException:
        doc.status = "failed"
        doc.extraction = {"error": "Файл сохранён. Повторите обработку позже."}
        db.commit()
        raise
    return {**serialize_doc(doc), **task}


@app.get("/api/documents/{id}/download")
def download(id: str, user=Depends(consent_user), db=Depends(get_db)):
    from urllib.parse import quote

    doc = owned(db, MedicalDocument, id, user)
    return Response(
        storage.read(doc.storage_key),
        media_type=doc.details["mime"],
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(doc.details["name"])
        },
    )


@app.post("/api/documents/{id}/retry")
def retry_doc(id: str, user=Depends(consent_user), db=Depends(get_db)):
    doc = owned(db, MedicalDocument, id, user)
    if doc.status not in ("failed", "review"):
        raise HTTPException(409, "Документ уже обрабатывается или сохранён.")
    doc.status = "queued"
    db.commit()
    return submit(db, user.id, "document", {"document_id": id})


@app.post("/api/documents/{id}/confirm")
def confirm_doc(
    id: str, body: Confirmation, user=Depends(consent_user), db=Depends(get_db)
):
    doc = db.scalar(
        select(MedicalDocument)
        .where(MedicalDocument.id == id, MedicalDocument.user_id == user.id)
        .with_for_update()
    )
    if not doc:
        raise HTTPException(404, "Документ не найден")
    if doc.status == "confirmed":
        return {"ok": True}
    if doc.status not in ("review", "failed"):
        raise HTTPException(409, "Дождитесь обработки документа.")
    for record in body.records:
        add_record(db, user, record, doc.id, doc.extraction.get("confidence"))
    if body.profile_update:
        save_profile(db, user, body.profile_update, "document:" + doc.id)
    doc.status = "confirmed"
    doc.extraction = {
        **doc.extraction,
        "verified": True,
        "confirmed_by": user.id,
        "confirmed_at": now().isoformat(),
    }
    audit(db, user.id, "document.confirm", id)
    db.commit()
    return {"ok": True}


@app.delete("/api/documents/{id}")
def delete_doc(id: str, user=Depends(consent_user), db=Depends(get_db)):
    doc = owned(db, MedicalDocument, id, user)
    storage.delete(doc.storage_key)
    db.delete(doc)
    db.commit()
    return {"ok": True}


@app.get("/api/chat")
def chat_history(user=Depends(consent_user), db=Depends(get_db)):
    return [
        {
            "id": m.id,
            "role": m.role,
            **m.content,
            "favorite": m.favorite,
            "created_at": m.created_at,
        }
        for m in db.scalars(
            select(ChatMessage)
            .where(ChatMessage.user_id == user.id)
            .order_by(ChatMessage.created_at)
            .limit(500)
        )
    ]


@app.post("/api/chat")
def chat(body: ChatInput, user=Depends(consent_user), db=Depends(get_db)):
    rate_limit("chat:" + user.id, 10)
    if config(db).get("features", {}).get("maintenance"):
        raise HTTPException(503, "Ассистент обновляется. Попробуйте чуть позже.")
    # A row lock serializes daily-limit reservations across Web and Telegram.
    db.scalar(
        select(Subscription).where(Subscription.user_id == user.id).with_for_update()
    )
    if usage(db, user.id)["remaining"] <= 0:
        raise HTTPException(
            429,
            "На сегодня вопросы закончились. Лимит обновится в 00:00 по Москве; ваши данные доступны.",
        )
    if db.scalar(
        select(Task).where(
            Task.user_id == user.id,
            Task.kind == "chat",
            Task.status.in_(["queued", "processing"]),
        )
    ):
        raise HTTPException(409, "Дождитесь ответа на предыдущий вопрос.")
    return submit(db, user.id, "chat", body.model_dump())


@app.put("/api/chat/{id}/favorite")
def favorite(
    id: str, body: dict = Body(...), user=Depends(consent_user), db=Depends(get_db)
):
    msg = owned(db, ChatMessage, id, user)
    msg.favorite = body.get("favorite") is True
    db.commit()
    return {"ok": True}


@app.get("/api/tasks/{id}")
def task(id: str, user=Depends(consent_user), db=Depends(get_db)):
    row = owned(db, Task, id, user)
    return {"id": row.id, "status": row.status, "result": row.result}


@app.post("/api/support")
def support(body: SupportInput, user=Depends(current_user), db=Depends(get_db)):
    rate_limit("support:" + user.id, 5, 3600)
    row = SupportRequest(user_id=user.id, data=body.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


@app.get("/api/support")
def my_support(user=Depends(current_user), db=Depends(get_db)):
    return [
        {"id": r.id, "status": r.status, **r.data}
        for r in db.scalars(
            select(SupportRequest).where(SupportRequest.user_id == user.id)
        )
    ]


@app.get("/api/notifications")
def notifications(user=Depends(current_user), db=Depends(get_db)):
    return [
        {"id": n.id, "status": n.status, "due_at": n.due_at, **n.data}
        for n in db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id, Notification.due_at <= now())
            .order_by(Notification.due_at.desc())
            .limit(30)
        )
    ]


@app.get("/api/subscription")
def subscription(user=Depends(current_user), db=Depends(get_db)):
    return usage(db, user.id)


@app.post("/api/subscription/checkout")
def checkout(body: dict = Body(...), user=Depends(consent_user), db=Depends(get_db)):
    rate_limit("checkout:" + user.id, 5, 3600)
    db.scalar(
        select(Subscription).where(Subscription.user_id == user.id).with_for_update()
    )
    pending = db.scalar(
        select(Payment).where(
            Payment.user_id == user.id,
            Payment.status == "pending",
        )
    )
    if (
        pending
        and not pending.provider_id
        and pending.created_at < now() - timedelta(hours=23)
    ):
        raise HTTPException(
            409,
            "Статус предыдущего платежа требует проверки. Обратитесь в поддержку перед повторной оплатой.",
        )
    if pending and pending.data.get("confirmation_url"):
        pending.recurring_consent = body.get("auto_renew") is True
        db.commit()
        return {"url": pending.data["confirmation_url"]}
    row = pending or Payment(
        user_id=user.id,
        amount=config(db)["price"],
        recurring_consent=body.get("auto_renew") is True,
    )
    db.add(row)
    db.commit()
    result = provider.create(row)
    row.provider_id = result["id"]
    row.data = {
        "confirmation_url": result.get("confirmation", {}).get("confirmation_url")
    }
    db.commit()
    if not row.data["confirmation_url"]:
        reconcile(db, row)
        return {"url": settings().app_url + "/subscription"}
    return {"url": row.data["confirmation_url"]}


@app.post("/api/subscription/cancel")
def cancel_subscription(user=Depends(current_user), db=Depends(get_db)):
    sub = db.scalar(
        select(Subscription).where(Subscription.user_id == user.id).with_for_update()
    )
    sub.auto_renew = False
    sub.payment_method = {}
    for pending in db.scalars(
        select(Payment).where(Payment.user_id == user.id, Payment.status == "pending")
    ):
        pending.recurring_consent = False
    if sub.status == "active":
        sub.status = "cancelled"
    audit(db, user.id, "subscription.cancel")
    db.commit()
    return usage(db, user.id)


@app.post("/api/payments/webhook")
def payment_webhook(body: dict = Body(...), db=Depends(get_db)):
    id = str(body.get("object", {}).get("id", ""))[:100]
    payment = db.scalar(select(Payment).where(Payment.provider_id == id))
    if not payment:
        # Providers can deliver before checkout stores provider_id. Retryable response.
        raise HTTPException(503, "Платёж ещё не зарегистрирован")
    reconcile(db, payment)
    return {"ok": True}


@app.get("/api/export")
def export(user=Depends(consent_user), db=Depends(get_db)):
    return {
        "profile": user.profile,
        "records": [
            serialize_record(r)
            for r in db.scalars(select(Record).where(Record.user_id == user.id))
        ],
        "documents": [
            serialize_doc(r)
            for r in db.scalars(
                select(MedicalDocument).where(MedicalDocument.user_id == user.id)
            )
        ],
        "chat": [
            {"role": r.role, **r.content}
            for r in db.scalars(
                select(ChatMessage).where(ChatMessage.user_id == user.id)
            )
        ],
    }


@app.delete("/api/account")
def delete_account(
    body: dict = Body(...), user=Depends(current_user), db=Depends(get_db)
):
    if body.get("confirmation") != "УДАЛИТЬ":
        raise HTTPException(422, "Введите УДАЛИТЬ для подтверждения.")
    for doc in db.scalars(
        select(MedicalDocument).where(MedicalDocument.user_id == user.id)
    ):
        storage.delete(doc.storage_key)
    db.delete(user)
    db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie("mama_session")
    return response


@app.get("/api/admin/overview")
def admin_overview(user=Depends(admin_user), db=Depends(get_db)):
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "documents": db.scalar(select(func.count()).select_from(MedicalDocument)),
        "questions": db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.role == "user")
        ),
        "errors": db.scalar(
            select(func.count()).select_from(Task).where(Task.status == "failed")
        ),
        "paid": db.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.status == "active", Subscription.ends_at > now())
        ),
        "trial": db.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.status == "trialing", Subscription.ends_at > now())
        ),
        "new_week": db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at > now() - timedelta(days=7))
        ),
    }


@app.get("/api/admin/users")
def admin_users(q: str = "", user=Depends(admin_user), db=Depends(get_db)):
    # Encrypted identity details are searched only inside the authorized process.
    result = []
    for row in db.scalars(select(User).order_by(User.created_at.desc()).limit(1000)):
        identities = list(
            db.scalars(select(Identity).where(Identity.user_id == row.id))
        )
        if (
            q.lower()
            not in json.dumps(
                [
                    row.id,
                    row.profile.get("name", ""),
                    [{"subject": i.subject, **i.info} for i in identities],
                ],
                ensure_ascii=False,
            ).lower()
        ):
            continue
        result.append(
            {
                "id": row.id,
                "name": row.profile.get("name", ""),
                "created_at": row.created_at,
                "blocked": row.blocked,
                "identities": [
                    {"provider": i.provider, "subject": i.subject, **i.info}
                    for i in identities
                ],
                "subscription": usage(db, row.id),
            }
        )
    audit(db, user.id, "admin.users.read")
    db.commit()
    return result


@app.get("/api/admin/users/{id}")
def admin_detail(id: str, user=Depends(admin_user), db=Depends(get_db)):
    row = db.get(User, id)
    if not row:
        raise HTTPException(404, "Не найдено")
    audit(db, user.id, "admin.profile.read", id)
    db.commit()
    return {
        "profile": row.profile,
        "subscription": usage(db, id),
        "documents": db.scalar(
            select(func.count())
            .select_from(MedicalDocument)
            .where(MedicalDocument.user_id == id)
        ),
    }


@app.patch("/api/admin/users/{id}")
def admin_change(
    id: str, body: dict = Body(...), user=Depends(admin_user), db=Depends(get_db)
):
    row = db.get(User, id)
    if not row:
        raise HTTPException(404, "Не найдено")
    if "blocked" in body:
        if row.id == user.id:
            raise HTTPException(400, "Нельзя заблокировать себя.")
        row.blocked = body["blocked"] is True
    sub = db.get(Subscription, id)
    if "months" in body:
        months = body["months"]
        if months not in (1, 3, 9):
            raise HTTPException(422, "Выберите 1, 3 или 9 месяцев")
        sub.ends_at = add_months(max(now(), sub.ends_at), months)
        sub.status = "active"
    if "daily_limit" in body:
        limit = body["daily_limit"]
        if limit is not None and (not isinstance(limit, int) or not 0 <= limit <= 1000):
            raise HTTPException(422, "Некорректный лимит")
        sub.daily_limit = limit
    if body.get("cancel"):
        sub.auto_renew = False
        sub.payment_method = {}
        sub.status = "cancelled"
    audit(db, user.id, "admin.user.update", id)
    db.commit()
    return {"ok": True}


@app.get("/api/admin/config")
def get_config(user=Depends(admin_user), db=Depends(get_db)):
    return config(db)


@app.put("/api/admin/config")
def put_config(body: AgentInput, user=Depends(admin_user), db=Depends(get_db)):
    row = db.get(AgentConfiguration, 1)
    row.data = body.model_dump()
    audit(db, user.id, "admin.config.update")
    db.commit()
    return row.data


@app.get("/api/admin/knowledge")
def admin_knowledge(user=Depends(admin_user), db=Depends(get_db)):
    return [
        {
            "id": k.id,
            "name": k.name,
            "enabled": k.enabled,
            "created_at": k.created_at,
            "size": len(k.content.encode()),
            **k.metadata_,
        }
        for k in db.scalars(select(KnowledgeDocument))
    ]


@app.post("/api/admin/knowledge")
async def upload_knowledge(
    file: UploadFile = File(...), user=Depends(admin_user), db=Depends(get_db)
):
    from .jobs import extract_text

    data = await file.read(settings().max_upload_mb * 1024 * 1024 + 1)
    mime = storage.validate(data, file.filename or "")
    if mime.startswith("image/"):
        raise HTTPException(422, "Для базы знаний используйте MD, TXT, PDF или DOCX.")
    # Parsing/indexing runs in a separate task through the same document pipeline below.
    key = user.id + "/knowledge-" + uid()
    storage.save(key, data)
    row = KnowledgeDocument(
        name=Path(file.filename).name[:180],
        content="",
        metadata_={"status": "queued", "storage_key": key, "mime": mime},
    )
    db.add(row)
    db.commit()
    audit(db, user.id, "admin.knowledge.upload", row.id)
    return submit(db, user.id, "knowledge", {"document_id": row.id})


@app.patch("/api/admin/knowledge/{id}")
def toggle_knowledge(
    id: str, body: dict = Body(...), user=Depends(admin_user), db=Depends(get_db)
):
    row = db.get(KnowledgeDocument, id)
    if not row:
        raise HTTPException(404, "Не найдено")
    row.enabled = body.get("enabled") is True
    audit(db, user.id, "admin.knowledge.toggle", id)
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/knowledge/{id}")
def delete_knowledge(id: str, user=Depends(admin_user), db=Depends(get_db)):
    row = db.get(KnowledgeDocument, id)
    if not row:
        raise HTTPException(404, "Не найдено")
    if row.metadata_.get("storage_key"):
        storage.delete(row.metadata_["storage_key"])
    db.delete(row)
    audit(db, user.id, "admin.knowledge.delete", id)
    db.commit()
    return {"ok": True}


@app.get("/api/admin/support")
def admin_support(user=Depends(admin_user), db=Depends(get_db)):
    return [
        {"id": r.id, "user_id": r.user_id, "status": r.status, **r.data}
        for r in db.scalars(
            select(SupportRequest).order_by(SupportRequest.created_at.desc()).limit(200)
        )
    ]


@app.patch("/api/admin/support/{id}")
def support_reply(
    id: str, body: dict = Body(...), user=Depends(admin_user), db=Depends(get_db)
):
    row = db.get(SupportRequest, id)
    if not row:
        raise HTTPException(404, "Не найдено")
    reply = str(body.get("reply", ""))[:5000]
    row.data = {**row.data, "reply": reply}
    row.status = "resolved"
    audit(db, user.id, "admin.support.reply", id)
    db.commit()
    return {"ok": True}


@app.get("/api/admin/audit")
def admin_audit(user=Depends(admin_user), db=Depends(get_db)):
    return [
        {
            "id": r.id,
            "actor": r.actor_id,
            "action": r.action,
            "target": r.target,
            "created_at": r.created_at,
        }
        for r in db.scalars(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(300)
        )
    ]


@app.post("/api/admin/payments/{id}/refund")
def refund(id: str, user=Depends(admin_user), db=Depends(get_db)):
    payment = db.scalar(select(Payment).where(Payment.id == id).with_for_update())
    if not payment or payment.status != "succeeded":
        raise HTTPException(409, "Платёж не доступен для возврата.")
    result = provider.refund(payment)
    payment.data = {
        **payment.data,
        "refund_id": result["id"],
        "refund_status": result["status"],
    }
    if result["status"] == "succeeded":
        payment.status = "refunded"
    audit(db, user.id, "admin.payment.refund", id)
    db.commit()
    return {"status": result["status"]}
