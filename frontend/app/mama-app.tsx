"use client";
import { useState, useEffect, useRef, FormEvent, ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Home,
  Files,
  MessageCircle,
  UserRound,
  ChartNoAxesCombined,
  CalendarDays,
  Plus,
  ArrowUpRight,
  ArrowRight,
  ChevronRight,
  ChevronLeft,
  Heart,
  Activity,
  Weight,
  Sparkles,
  ShieldCheck,
  Send,
  Upload,
  FileText,
  Check,
  X,
  Menu,
  Bell,
  LogOut,
  Download,
  Trash2,
  Star,
  LoaderCircle,
  LifeBuoy,
  Settings,
  Clock,
  CheckCircle2,
  Leaf,
  Search,
} from "lucide-react";
import {
  api,
  post,
  put,
  Item,
  demoProfile,
  demoRecords,
  demoDocuments,
  demoChat,
  formatDate,
  labels,
  statusLabels,
  pollTask,
} from "./lib";

declare global {
  interface Window {
    google: any;
    Telegram: any;
  }
}
const navigation = [
  ["/app", "Главная", Home],
  ["/data", "Мои данные", Files],
  ["/dynamics", "Моя динамика", ChartNoAxesCombined],
  ["/chat", "AI-ассистент", MessageCircle],
  ["/profile", "Моя беременность", UserRound],
] as const;
const dateInput = () => new Date().toISOString().slice(0, 10);
function Button({
  children,
  onClick,
  secondary = false,
  disabled = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  secondary?: boolean;
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={"button " + (secondary ? "secondary" : "primary")}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
function Empty({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Leaf size={32} />
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    ref.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "Tab") {
        const els = ref.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input,select,textarea,a[href]",
        );
        if (!els?.length) return;
        const first = els[0],
          last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = previous;
      before?.focus();
    };
  }, [close]);
  return (
    <div
      className="modal-shade"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="modal"
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="Закрыть" onClick={close}>
            <X />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
function Chart({
  records,
  kind = "weight",
}: {
  records: Item[];
  kind?: string;
}) {
  const [selected, setSelected] = useState<Item | null>(null);
  const values = records
    .filter((r) => r.kind === kind && typeof r.value === "number")
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));
  if (values.length < 2)
    return (
      <Empty
        title="Пока недостаточно данных для графика"
        text="Когда появятся несколько измерений, здесь будет видна их динамика."
      />
    );
  const numbers = values.map((v) => v.value),
    lo = Math.min(...numbers) - 0.5,
    hi = Math.max(...numbers) + 0.5;
  const pts = values.map((r, i) => ({
    x: 40 + (i * 460) / (values.length - 1),
    y: 145 - ((r.value - lo) / (hi - lo)) * 115,
    r,
  }));
  const d = pts.map((p) => `${p.x},${p.y}`).join(" ");
  return (
    <div className="chart">
      <svg
        viewBox="0 0 540 190"
        role="img"
        aria-label={"Динамика: " + labels[kind]}
      >
        <defs>
          <linearGradient id={"fill-" + kind} x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#299b91" stopOpacity=".20" />
            <stop offset="1" stopColor="#299b91" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[35, 85, 135].map((y) => (
          <line
            key={y}
            x1="40"
            x2="500"
            y1={y}
            y2={y}
            stroke="#edf0ed"
            strokeDasharray="4 4"
          />
        ))}
        <polygon points={`40,155 ${d} 500,155`} fill={`url(#fill-${kind})`} />
        <polyline
          points={d}
          fill="none"
          stroke="#2e9288"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        {pts.map((p, i) => (
          <g
            key={i}
            role="button"
            tabIndex={0}
            aria-label={`${formatDate(p.r.recorded_at)}: ${p.r.value} ${p.r.unit}`}
            onClick={() => setSelected(p.r)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setSelected(p.r);
            }}
          >
            <circle cx={p.x} cy={p.y} r="13" fill="transparent" />
            <circle
              cx={p.x}
              cy={p.y}
              r="4"
              fill="white"
              stroke="#2e9288"
              strokeWidth="2"
            />
            {(i === 0 ||
              i === pts.length - 1 ||
              i === Math.floor(pts.length / 2)) && (
              <text
                x={p.x}
                y="180"
                textAnchor="middle"
                fill="#85938f"
                fontSize="12.65"
              >
                {formatDate(p.r.recorded_at)}
              </text>
            )}
          </g>
        ))}
      </svg>
      {selected && (
        <p className="chart-detail">
          {formatDate(selected.recorded_at)} ·{" "}
          <b>
            {selected.value} {selected.unit}
          </b>{" "}
          · Источник:{" "}
          {selected.document_id
            ? "анализ"
            : selected.provenance?.source === "demo"
              ? "демо"
              : "введено вами"}
        </p>
      )}
    </div>
  );
}

export default function MamaApp() {
  const path = usePathname(),
    router = useRouter();
  const [loading, setLoading] = useState(true),
    [me, setMe] = useState<Item | null>(null),
    [config, setConfig] = useState<Item>({
      price: 499,
      trial_days: 30,
      bot_username: "beremen_ai_bot",
    }),
    [records, setRecords] = useState<Item[]>([]),
    [documents, setDocuments] = useState<Item[]>([]),
    [messages, setMessages] = useState<Item[]>([]),
    [notice, setNotice] = useState(""),
    [modal, setModal] = useState(""),
    [busy, setBusy] = useState(false),
    [question, setQuestion] = useState(""),
    [mobile, setMobile] = useState(false),
    [review, setReview] = useState<Item | null>(null),
    [filter, setFilter] = useState("all"),
    [chartKind, setChartKind] = useState("weight"),
    [notificationList, setNotificationList] = useState<Item[]>([]);
  const fileRef = useRef<HTMLInputElement>(null),
    chatBottom = useRef<HTMLDivElement>(null);
  const demo = !me,
    profile = me?.profile || demoProfile,
    rows = demo ? demoRecords : records,
    docs = demo ? demoDocuments : documents,
    chat = demo ? demoChat : messages;
  const accountName =
    me?.identities?.find((identity: Item) => identity.provider === "google")
      ?.name ||
    me?.identities?.find((identity: Item) => identity.provider === "telegram")
      ?.name ||
    profile.name ||
    "М";
  const avatarLetter = accountName.trim().charAt(0).toUpperCase() || "М";
  const g =
    me?.gestation ||
    (demo
      ? {
          weeks: 18,
          days: 4,
          remaining: 150,
          due_date: new Date(Date.now() + 150 * 86400000).toISOString(),
        }
      : null);
  const title =
    navigation.find((n) => n[0] === path)?.[1] ||
    (
      {
        "/subscription": "Подписка",
        "/support": "Помощь",
        "/admin": "Neyrix Mama Admin",
        "/timeline": "История беременности",
        "/privacy": "Обработка данных",
      } as Item
    )[path] ||
    "Главная";
  const toast = (message: string) => {
    setNotice(message);
  };
  async function refresh() {
    try {
      const current = await api("/me");
      setMe(current);
      if (current.consented) {
        const [a, b, c] = await Promise.all([
          api("/records"),
          api("/documents"),
          api("/chat"),
        ]);
        setRecords(a);
        setDocuments(b);
        setMessages(c);
      }
    } catch (e) {
      if ((e as Error).message.includes("Войдите")) setMe(null);
      else toast((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    api("/public-config")
      .then(setConfig)
      .catch(() => {});
    refresh();
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-web-app.js";
    script.onload = async () => {
      const tg = window.Telegram?.WebApp;
      if (tg?.initData) {
        tg.ready();
        try {
          await post("/auth/telegram", { init_data: tg.initData });
          await refresh();
        } catch (e) {
          toast((e as Error).message);
        }
      }
    };
    document.head.appendChild(script);
    return () => script.remove();
  }, []);
  useEffect(() => {
    setMobile(false);
  }, [path]);
  useEffect(() => {
    chatBottom.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [messages, busy]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 9000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (
      !me ||
      !documents.some((d) => ["queued", "processing"].includes(d.status))
    )
      return;
    const timer = setInterval(
      () =>
        api("/documents")
          .then(setDocuments)
          .catch(() => {}),
      3000,
    );
    return () => clearInterval(timer);
  }, [me, documents]);
  const gate = (action: () => void) => {
    if (demo) setModal("login");
    else if (!me?.consented) setModal("consent");
    else action();
  };
  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function uploadFile(file: File) {
    gate(() =>
      run(async () => {
        const form = new FormData();
        form.append("file", file);
        await api("/documents", { method: "POST", body: form });
        await refresh();
        toast(
          "Документ сохранён. Сообщим, когда данные будут готовы к проверке.",
        );
        router.push("/data");
      }),
    );
  }
  async function sendQuestion(e?: FormEvent) {
    e?.preventDefault();
    if (!question.trim() || busy) return;
    gate(() =>
      run(async () => {
        const text = question;
        const task = await post("/chat", { text });
        setQuestion("");
        setMessages((m) => [...m, { id: "pending", role: "user", text }]);
        router.push("/chat");
        try {
          await pollTask(task.task_id);
        } finally {
          await refresh();
        }
      }),
    );
  }
  const weights = rows
    .filter((r) => r.kind === "weight")
    .sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
  const latestWeight = weights[0]?.value || profile.current_weight;
  const pressure = rows.find((r) => r.kind === "blood_pressure");
  const nextEvent = rows
    .filter((r) => r.kind === "event" && new Date(r.recorded_at) > new Date())
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at))[0];
  const quickChat = (
    <form className="quick-form" onSubmit={sendQuestion}>
      <Sparkles size={20} />
      <input
        aria-label="Вопрос ассистенту"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Что вас волнует сегодня?"
        maxLength={6000}
      />
      <button disabled={busy || !question.trim()} aria-label="Отправить вопрос">
        {busy ? (
          <LoaderCircle className="spin" size={20} />
        ) : (
          <ArrowRight size={20} />
        )}
      </button>
    </form>
  );
  function Dashboard() {
    return (
      <>
        <div className="welcome">
          <div>
            <p className="eyebrow">ВАШЕ СПОКОЙНОЕ ПРОСТРАНСТВО</p>
            <h1>
              Добрый день{profile.name ? ", " + profile.name : ""}{" "}
              <span className="sun">☀</span>
            </h1>
            <p>Маленькие шаги. Большие перемены. Мы рядом.</p>
          </div>
          <button
            className="button secondary"
            onClick={() => gate(() => setModal("record"))}
          >
            <Plus size={18} /> Добавить данные
          </button>
        </div>
        <div className="dashboard-grid">
          <section className="pregnancy-card">
            <div className="pregnancy-text">
              <span className="pill">
                {g
                  ? g.weeks < 14
                    ? "Первый триместр"
                    : g.weeks < 28
                      ? "Второй триместр"
                      : "Третий триместр"
                  : "Моя беременность"}
              </span>
              <p className="soft-label">Ваша беременность сегодня</p>
              <h2>
                {g ? (
                  <>
                    {g.weeks} <small>недель</small> {g.days} <small>дня</small>
                  </>
                ) : (
                  "Всё начинается с вас"
                )}
              </h2>
              <p>
                {g
                  ? demo
                    ? "У многих появляются первые отчётливые шевеления. План обследований уточняйте у вашего врача."
                    : me?.week_summary ||
                      "Каждая неделя — новая глава вашей истории."
                  : "Укажите срок беременности, чтобы настроить приложение."}
              </p>
              <div className="pregnancy-progress">
                <div
                  style={{
                    width: `${Math.min(100, ((g?.weeks || 0) / 40) * 100)}%`,
                  }}
                />
              </div>
              <div className="progress-labels">
                <span>Начало пути</span>
                <Heart size={13} />
                <span>Встреча с малышом</span>
              </div>
              <div className="pregnancy-footer">
                <span>
                  ПДР <b>{g ? formatDate(g.due_date) : "пока не указана"}</b>
                </span>
                <span>
                  {g
                    ? `Примерно ${g.remaining} дней до встречи`
                    : "Заполните профиль"}
                </span>
              </div>
            </div>
            <div className="pregnancy-art">
              <img src="/logo.png" alt="Neyrix Mama — забота о маме и малыше" />
              <span className="art-caption">
                <Heart size={13} /> Растём вместе
              </span>
            </div>
          </section>
          <section className="card next-card">
            <span className="icon-tile peach">
              <CalendarDays />
            </span>
            <p className="eyebrow">БЛИЖАЙШЕЕ</p>
            <h3>{nextEvent?.title || "Планы на ближайшие дни"}</h3>
            <p>
              {nextEvent
                ? formatDate(nextEvent.recorded_at)
                : "Добавьте приём или обследование, чтобы всё было под рукой."}
            </p>
            {nextEvent ? (
              <div className="event-count">
                Через{" "}
                {Math.max(
                  0,
                  Math.ceil(
                    (new Date(nextEvent.recorded_at).getTime() - Date.now()) /
                      86400000,
                  ),
                )}{" "}
                дней
              </div>
            ) : null}
            <button
              className="text-button"
              onClick={() => gate(() => setModal("record"))}
            >
              {nextEvent ? "Открыть календарь" : "Добавить событие"}{" "}
              <ArrowRight size={16} />
            </button>
          </section>
          <section className="metrics">
            <div className="section-title">
              <h2>Мои показатели</h2>
              <Link href="/dynamics">
                Вся динамика <ChevronRight size={16} />
              </Link>
            </div>
            <div className="metric-grid">
              <div className="card metric">
                <span className="icon-tile mint">
                  <Weight size={20} />
                </span>
                <span>Текущий вес</span>
                <strong>
                  {latestWeight || "—"} <small>кг</small>
                </strong>
                <p>
                  {latestWeight && profile.pre_weight
                    ? `+${(latestWeight - profile.pre_weight).toFixed(1)} кг с начала беременности`
                    : "Добавьте первое измерение"}
                </p>
              </div>
              <div className="card metric">
                <span className="icon-tile blue">
                  <Heart size={20} />
                </span>
                <span>Давление</span>
                <strong>
                  {pressure ? `${pressure.value}/${pressure.secondary}` : "—"}{" "}
                  <small>мм рт. ст.</small>
                </strong>
                <p>
                  {pressure
                    ? formatDate(pressure.recorded_at)
                    : "Измерения появятся здесь"}
                </p>
              </div>
              <div className="card metric">
                <span className="icon-tile peach">
                  <Activity size={20} />
                </span>
                <span>Самочувствие</span>
                <strong className="metric-text">Как вы сегодня?</strong>
                <button
                  className="text-button"
                  onClick={() => gate(() => setModal("record"))}
                >
                  Сделать заметку <Plus size={14} />
                </button>
              </div>
            </div>
          </section>
          <section className="card assistant-teaser">
            <span className="icon-tile mint">
              <Sparkles />
            </span>
            <h3>Можно просто спросить</h3>
            <p>Об анализах, питании, тренировках и всём, что волнует.</p>
            <Link className="text-button" href="/chat">
              Спросить Neyrix Mama <ArrowRight size={17} />
            </Link>
            <div className="mini-note">
              <ShieldCheck size={15} /> С учётом вашей беременности
            </div>
          </section>
          <section className="card weight-chart">
            <div className="section-title">
              <div>
                <h2>Плавно меняемся</h2>
                <p>Динамика вашего веса</p>
              </div>
              <span className="pill neutral">Последние измерения</span>
            </div>
            <Chart records={rows} />
          </section>
          <section className="card recent">
            <div className="section-title">
              <h2>Последние данные</h2>
              <Link href="/data">
                <ArrowUpRight size={20} />
                <span className="sr-only">Все данные</span>
              </Link>
            </div>
            {docs.slice(0, 2).map((d) => (
              <button
                className="document-row"
                key={d.id}
                onClick={() =>
                  gate(() => {
                    setReview(d);
                    setModal("review");
                  })
                }
              >
                <span className="icon-tile pale">
                  <FileText size={20} />
                </span>
                <span>
                  <b>{d.extraction?.title || d.name}</b>
                  <small>
                    {formatDate(d.created_at)} · {statusLabels[d.status]}
                  </small>
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
            {!docs.length && (
              <p className="muted">
                Здесь будут храниться ваши анализы. Добавьте первый документ.
              </p>
            )}
            <button
              className="add-document"
              onClick={() => gate(() => fileRef.current?.click())}
            >
              <Plus size={17} /> Добавить анализ или документ
            </button>
          </section>
          <section className="card quick-question">
            <div>
              <span className="icon-tile mint">
                <MessageCircle size={20} />
              </span>
              <h3>Спросить Neyrix Mama</h3>
            </div>
            {quickChat}
          </section>
        </div>
        <div className="quiet-footer">
          <ShieldCheck size={15} />
          <span>
            Ваши данные — только для вас. Neyrix Mama помогает понимать
            информацию и не заменяет врача.
          </span>
        </div>
      </>
    );
  }
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <Link href="/app" className="brand">
          <img src="/icon.png" alt="" />
          <span>
            Neyrix <b>Mama</b>
            <small>Рядом с самого начала</small>
          </span>
        </Link>
        <div className="nav-caption">МОЁ ПРОСТРАНСТВО</div>
        <nav>
          {navigation.map(([href, label, Icon]) => (
            <Link
              key={href}
              href={href}
              className={
                path === href || (path === "/" && href === "/app")
                  ? "active"
                  : ""
              }
            >
              <Icon size={20} />
              {label}
              {href === "/chat" && <span className="ai-dot">AI</span>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="trial-card">
            <Sparkles size={21} />
            <h4>Забота без спешки</h4>
            <p>
              Первый месяц — бесплатно.
              <br />
              Познакомимся поближе?
            </p>
            <Link href="/subscription">
              О подписке <ArrowUpRight size={16} />
            </Link>
          </div>
          <Link className="support-link" href="/support">
            <LifeBuoy size={19} /> Помощь и поддержка
          </Link>
          <div className="sidebar-profile">
            <span className="avatar">{avatarLetter}</span>
            <div>
              <b>{demo ? "Ваш профиль" : profile.name || "Моя беременность"}</b>
              <small>{demo ? "Начните свою историю" : "Neyrix Mama"}</small>
            </div>
            <button
              className="icon-button"
              aria-label={demo ? "Войти" : "Выйти"}
              onClick={() =>
                demo
                  ? setModal("login")
                  : run(async () => {
                      await post("/auth/logout");
                      setMe(null);
                      setRecords([]);
                      setDocuments([]);
                      setMessages([]);
                      router.push("/app");
                    })
              }
            >
              {demo ? <ArrowRight size={18} /> : <LogOut size={18} />}
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button hamburger"
              aria-label="Меню"
              onClick={() => setMobile(!mobile)}
            >
              <Menu />
            </button>
            <span>Neyrix Mama</span>
            <ChevronRight size={14} />
            <b>{title}</b>
          </div>
          <div className="top-actions">
            {demo ? (
              <>
                <span className="demo-badge">Демо</span>
                <button
                  className="button small primary"
                  onClick={() => setModal("login")}
                >
                  Создать мой профиль <ArrowUpRight size={15} />
                </button>
              </>
            ) : (
              <>
                <span className="desktop-only muted">Рада быть рядом</span>
                <button
                  className="icon-button"
                  aria-label="Уведомления"
                  onClick={() =>
                    run(async () => {
                      setNotificationList(await api("/notifications"));
                      setModal("notifications");
                    })
                  }
                >
                  <Bell size={19} />
                </button>
                <span className="avatar small-avatar">{avatarLetter}</span>
              </>
            )}
          </div>
        </header>
        {demo && (
          <div className="demo-strip">
            <span>
              <span className="little-dot" /> Это пример вашей будущей истории.
              Все данные на экране — демонстрационные.
            </span>
            <button onClick={() => setModal("login")}>
              Начать свою <ArrowRight size={14} />
            </button>
          </div>
        )}
        <main>
          {loading ? (
            <div className="loading-screen">
              <LoaderCircle className="spin" />
              <p>Открываем ваше пространство…</p>
            </div>
          ) : (
            <>
              {path === "/" && demo && (
                <section className="landing-hero">
                  <p className="eyebrow">
                    NEYRiX MAMA — ПЕРСОНАЛЬНЫЙ AI-АССИСТЕНТ
                  </p>
                  <h2>Вся беременность — в одном месте</h2>
                  <p>
                    Neyrix Mama помогает хранить анализы и УЗИ, отслеживать
                    динамику, понимать результаты и получать персональные ответы
                    AI-ассистента с учётом срока беременности.
                  </p>
                  <div className="button-row">
                    <Button onClick={() => setModal("login")}>
                      Начать бесплатно <ArrowRight size={17} />
                    </Button>
                    <a
                      className="button secondary"
                      href={`https://t.me/${config.bot_username}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Send size={17} /> Открыть в Telegram
                    </a>
                  </div>
                  <p className="fine-print">
                    Первый месяц бесплатно · Не заменяет врача. Помогает лучше
                    понимать информацию о вашей беременности.
                  </p>
                </section>
              )}
              {(path === "/" || path === "/app") && Dashboard()}
              {path === "/data" && (
                <>
                  <PageTitle
                    eyebrow="ВСЁ В ОДНОМ МЕСТЕ"
                    title="Мои данные"
                    text="Анализы, УЗИ и важные записи вашей беременности."
                    action={
                      <Button
                        onClick={() => gate(() => fileRef.current?.click())}
                      >
                        <Plus size={18} /> Добавить документ
                      </Button>
                    }
                  />
                  <div className="tabs">
                    {[
                      ["all", "Все данные"],
                      ["documents", "Документы"],
                      ["lab", "Анализы"],
                      ["ultrasound", "УЗИ"],
                      ["medication", "Лекарства"],
                      ["symptom", "Самочувствие"],
                    ].map(([v, t]) => (
                      <button
                        className={filter === v ? "active" : ""}
                        key={v}
                        onClick={() => setFilter(v)}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                  <div
                    className="upload-zone"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (e.dataTransfer.files[0])
                        uploadFile(e.dataTransfer.files[0]);
                    }}
                  >
                    <Upload size={26} />
                    <div>
                      <h3>Добавить анализ или документ</h3>
                      <p>
                        Перетащите файл или выберите на устройстве. Фото, PDF,
                        DOCX, TXT · до 15 МБ
                      </p>
                    </div>
                    <Button
                      secondary
                      onClick={() => gate(() => fileRef.current?.click())}
                    >
                      Выбрать файл
                    </Button>
                  </div>
                  <div className="card data-list">
                    {["all", "documents"].includes(filter) &&
                      docs.map((d) => (
                        <button
                          className="document-row"
                          key={d.id}
                          onClick={() =>
                            gate(() => {
                              setReview(d);
                              setModal("review");
                            })
                          }
                        >
                          <span className="icon-tile mint">
                            <FileText />
                          </span>
                          <span>
                            <b>{d.extraction?.title || d.name}</b>
                            <small>
                              {d.name} · {formatDate(d.created_at)}
                            </small>
                          </span>
                          <span
                            className={
                              "pill " +
                              (d.status === "review" ? "peach" : "neutral")
                            }
                          >
                            {statusLabels[d.status]}
                          </span>
                          <ChevronRight size={18} />
                        </button>
                      ))}
                    {filter !== "documents" &&
                      rows
                        .filter((r) => filter === "all" || r.kind === filter)
                        .map((r) => (
                          <div className="document-row" key={r.id}>
                            <span className="icon-tile pale">
                              <Activity size={20} />
                            </span>
                            <span>
                              <b>{r.title || labels[r.kind]}</b>
                              <small>
                                {formatDate(r.recorded_at)} ·{" "}
                                {r.notes || labels[r.kind]}
                              </small>
                            </span>
                            <strong>
                              {r.value ?? ""}
                              {r.secondary ? "/" + r.secondary : ""} {r.unit}
                            </strong>
                          </div>
                        ))}
                    {!docs.length && !rows.length && (
                      <Empty
                        title="Здесь будут храниться ваши анализы"
                        text="Добавьте первый документ — фото, скриншот или PDF."
                      />
                    )}
                    <button
                      className="add-document"
                      onClick={() => gate(() => setModal("record"))}
                    >
                      <Plus size={17} /> Добавить запись вручную
                    </button>
                  </div>
                </>
              )}
              {path === "/dynamics" && (
                <>
                  <PageTitle
                    eyebrow="ВИДЕТЬ ИЗМЕНЕНИЯ"
                    title="Моя динамика"
                    text="Не отдельные цифры, а ваша история во времени."
                    action={
                      <Button onClick={() => gate(() => setModal("record"))}>
                        <Plus size={18} /> Добавить измерение
                      </Button>
                    }
                  />
                  <div className="tabs">
                    {[
                      ["weight", "Вес"],
                      ["blood_pressure", "Давление"],
                      ["lab", "Анализы"],
                    ].map(([v, t]) => (
                      <button
                        key={v}
                        className={chartKind === v ? "active" : ""}
                        onClick={() => setChartKind(v)}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                  <div className="card">
                    <h2>{labels[chartKind]}</h2>
                    {chartKind === "lab" ? (
                      <LabCharts records={rows} />
                    ) : (
                      <Chart records={rows} kind={chartKind} />
                    )}
                    <p className="muted">
                      Нажмите на точку, чтобы посмотреть дату и источник.
                      Оценивать показатели важно с учётом срока и рекомендаций
                      врача.
                    </p>
                  </div>
                  <Link className="text-button spaced" href="/timeline">
                    Вся история беременности <ArrowRight size={17} />
                  </Link>
                </>
              )}
              {path === "/timeline" && (
                <>
                  <PageTitle
                    eyebrow="ВАША ИСТОРИЯ"
                    title="Беременность день за днём"
                    text="Измерения, заметки и события в одной ленте."
                  />
                  <div className="card">
                    {rows.map((r) => (
                      <div className="timeline-row" key={r.id}>
                        <span className="timeline-dot" />
                        <div>
                          <small>{formatDate(r.recorded_at)}</small>
                          <h3>{r.title || labels[r.kind]}</h3>
                          <p>
                            {r.value} {r.unit} {r.notes}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
              {path === "/chat" && (
                <>
                  <PageTitle
                    eyebrow="МОЖНО ПРОСТО СПРОСИТЬ"
                    title="Спросить Neyrix Mama"
                    text="Спокойно разберёмся в том, что вас волнует."
                    action={
                      <span className="pill mint">
                        <Sparkles size={14} />
                        {demo
                          ? "Пример диалога"
                          : `Осталось ${me?.subscription?.remaining} из ${me?.subscription?.limit} вопросов`}
                      </span>
                    }
                  />
                  <div className="chat-layout">
                    <section className="card chat-panel">
                      <div className="chat-profile">
                        <img src="/icon.png" alt="" />
                        <div>
                          <b>Neyrix Mama</b>
                          <small>Ваш персональный AI-ассистент</small>
                        </div>
                        <ShieldCheck size={20} />
                      </div>
                      <div className="messages">
                        {!chat.length && (
                          <Empty
                            title="Можно спросить что угодно о беременности"
                            text="Начните с вопроса, который волнует вас сейчас."
                          />
                        )}
                        {chat.map((m) => (
                          <div key={m.id} className={"message " + m.role}>
                            <div className="message-bubble">
                              {m.text}
                              {m.sources?.length > 0 && (
                                <details>
                                  <summary>На что опирается ответ</summary>
                                  {m.sources.map((s: Item, i: number) => (
                                    <p key={i}>
                                      {i + 1}. {s.topic} · {s.source_date}
                                    </p>
                                  ))}
                                </details>
                              )}
                            </div>
                            {m.role === "assistant" && (
                              <div className="message-actions">
                                <button
                                  onClick={() =>
                                    gate(() =>
                                      run(async () => {
                                        await put(
                                          "/chat/" + m.id + "/favorite",
                                          { favorite: !m.favorite },
                                        );
                                        await refresh();
                                      }),
                                    )
                                  }
                                >
                                  <Star
                                    size={14}
                                    fill={m.favorite ? "currentColor" : "none"}
                                  />{" "}
                                  Сохранить
                                </button>
                                <button
                                  onClick={() =>
                                    setQuestion(
                                      "Расскажите подробнее о предыдущем ответе",
                                    )
                                  }
                                >
                                  Подробнее
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                        {busy && (
                          <p className="thinking">
                            <LoaderCircle size={16} className="spin" />{" "}
                            Обдумываю ваш вопрос…
                          </p>
                        )}
                        <div ref={chatBottom} />
                      </div>
                      <div className="chat-compose">
                        {quickChat}
                        <p>
                          Не заменяет врача. При экстренных симптомах звоните
                          112 или 103.
                        </p>
                      </div>
                    </section>
                    <aside className="chat-context card">
                      <span className="icon-tile mint">
                        <Leaf />
                      </span>
                      <h3>Мы уже знакомы</h3>
                      <p>
                        {g
                          ? `${g.weeks} недель ${g.days} дня`
                          : "Срок пока не указан"}
                      </p>
                      <p>
                        Ассистент учитывает ваш профиль и подтверждённые
                        показатели.
                      </p>
                      <hr />
                      <h4>С чего начать</h4>
                      {[
                        "Какие обследования предстоят на моей неделе?",
                        "Что обсудить с врачом на ближайшем приёме?",
                        "Как адаптировать тренировки?",
                      ].map((t) => (
                        <button
                          key={t}
                          className="suggestion"
                          onClick={() => setQuestion(t)}
                        >
                          {t}
                          <ArrowUpRight size={16} />
                        </button>
                      ))}
                      <button
                        className="text-button"
                        onClick={() => gate(() => fileRef.current?.click())}
                      >
                        <Upload size={16} /> Добавить анализ
                      </button>
                    </aside>
                  </div>
                </>
              )}
              {path === "/profile" && (
                <>
                  <PageTitle
                    eyebrow="НЕМНОГО О ВАС"
                    title="Моя беременность"
                    text="Чем больше мы знаем, тем полезнее можем быть. Любой ответ можно изменить."
                  />
                  {demo ? (
                    <div className="card">
                      <Empty
                        title="Начните свою историю"
                        text="Несколько вопросов помогут настроить приложение под вашу беременность."
                        action={
                          <Button onClick={() => setModal("login")}>
                            Создать мой профиль
                          </Button>
                        }
                      />
                    </div>
                  ) : (
                    <>
                      <ProfileEditor
                        initial={profile}
                        busy={busy}
                        onSave={(value) =>
                          run(async () => {
                            await put("/profile", value);
                            await refresh();
                            toast("Данные профиля сохранены.");
                          })
                        }
                      />
                      <section className="card spaced">
                        <h2>Связь и приватность</h2>
                        <p>
                          Ваши документы и история доступны в Web и Telegram.
                        </p>
                        <div className="identity-list">
                          {me?.identities?.map((i: Item) => (
                            <span key={i.provider} className="pill mint">
                              <Check size={14} />
                              {i.provider === "google"
                                ? "Google"
                                : "Telegram"}{" "}
                              {i.email || i.username || ""}
                            </span>
                          ))}
                        </div>
                        <div className="button-row">
                          <Button
                            secondary
                            onClick={() => gate(() => setModal("link"))}
                          >
                            Подключить Telegram
                          </Button>
                          <Button
                            secondary
                            onClick={() =>
                              run(async () => {
                                const data = await api("/export");
                                const url = URL.createObjectURL(
                                  new Blob([JSON.stringify(data, null, 2)], {
                                    type: "application/json",
                                  }),
                                );
                                const a = document.createElement("a");
                                a.href = url;
                                a.download = "neyrix-mama-data.json";
                                a.click();
                                URL.revokeObjectURL(url);
                              })
                            }
                          >
                            <Download size={16} /> Скачать мои данные
                          </Button>
                        </div>
                        <label className="check-label">
                          <input
                            type="checkbox"
                            checked={me?.preferences?.reminders || false}
                            onChange={(e) =>
                              run(async () => {
                                await put("/preferences", {
                                  ...me?.preferences,
                                  reminders: e.target.checked,
                                });
                                await refresh();
                              })
                            }
                          />{" "}
                          Напоминания о моих событиях в Telegram
                        </label>
                        <label className="check-label">
                          <input
                            type="checkbox"
                            checked={me?.preferences?.weekly || false}
                            onChange={(e) =>
                              run(async () => {
                                await put("/preferences", {
                                  ...me?.preferences,
                                  weekly: e.target.checked,
                                });
                                await refresh();
                              })
                            }
                          />{" "}
                          Сообщать о новой неделе беременности
                        </label>
                        <div className="button-row">
                          <Button
                            secondary
                            onClick={() =>
                              gate(() =>
                                run(async () => {
                                  const history = await api("/profile/history");
                                  setReview({ history });
                                  setModal("history");
                                }),
                              )
                            }
                          >
                            История изменений профиля
                          </Button>
                          <button
                            className="danger-link"
                            onClick={() => setModal("delete")}
                          >
                            Удалить мои данные
                          </button>
                        </div>
                      </section>
                    </>
                  )}
                </>
              )}
              {path === "/subscription" && (
                <>
                  <PageTitle
                    eyebrow="ЗАБОТА, КОТОРАЯ РЯДОМ"
                    title="Одна подписка. Вся беременность."
                    text="Все важные инструменты — в одном спокойном пространстве."
                  />
                  <SubscriptionPanel
                    demo={demo}
                    config={config}
                    subscription={me?.subscription}
                    busy={busy}
                    onStart={(renew: boolean) =>
                      gate(() =>
                        run(async () => {
                          const r = await post("/subscription/checkout", {
                            auto_renew: renew,
                          });
                          window.location.href = r.url;
                        }),
                      )
                    }
                    onCancel={() =>
                      run(async () => {
                        await post("/subscription/cancel");
                        await refresh();
                        toast(
                          "Автопродление отключено. Доступ сохранится до конца оплаченного периода.",
                        );
                      })
                    }
                  />
                </>
              )}
              {path === "/support" && (
                <>
                  <PageTitle
                    eyebrow="МЫ НА СВЯЗИ"
                    title="Помощь и поддержка"
                    text="Расскажите, что не получилось. Поможем разобраться."
                  />
                  <SupportPanel
                    demo={demo}
                    busy={busy}
                    send={(data) =>
                      gate(() =>
                        run(async () => {
                          const r = await post("/support", data);
                          toast(
                            "Обращение создано. Номер: " + r.id.slice(0, 8),
                          );
                          setModal("support-sent");
                        }),
                      )
                    }
                  />
                </>
              )}
              {path === "/privacy" && <Privacy />}
              {path === "/admin" && <AdminPanel onError={toast} />}
              {![
                "/",
                "/app",
                "/data",
                "/dynamics",
                "/timeline",
                "/chat",
                "/profile",
                "/subscription",
                "/support",
                "/admin",
                "/privacy",
              ].includes(path) && (
                <Empty
                  title="Страница не найдена"
                  text="Вернитесь на главную, чтобы продолжить."
                  action={<Link href="/app">На главную</Link>}
                />
              )}
            </>
          )}
        </main>
        <nav className="bottom-nav">
          {navigation
            .filter((n) => n[0] !== "/dynamics")
            .map(([href, label, Icon]) => (
              <Link
                key={href}
                href={href}
                className={path === href ? "active" : ""}
              >
                <Icon size={21} />
                <span>
                  {href === "/profile"
                    ? "Профиль"
                    : href === "/data"
                      ? "Данные"
                      : href === "/chat"
                        ? "Ассистент"
                        : label}
                </span>
              </Link>
            ))}
        </nav>
      </div>
      <input
        ref={fileRef}
        hidden
        type="file"
        accept=".jpg,.jpeg,.png,.heic,.heif,.pdf,.docx,.txt"
        onChange={(e) => {
          if (e.target.files?.[0]) uploadFile(e.target.files[0]);
          e.target.value = "";
        }}
      />
      {notice && (
        <div className="toast" role="status">
          <span>{notice}</span>
          <button
            aria-label="Закрыть уведомление"
            onClick={() => setNotice("")}
          >
            <X size={18} />
          </button>
        </div>
      )}
      {modal === "login" && (
        <Modal
          title="Добро пожаловать в Neyrix Mama"
          close={() => setModal("")}
        >
          <Login
            config={config}
            onDone={async () => {
              setModal("");
              await refresh();
              router.push("/profile");
            }}
            onError={toast}
          />
        </Modal>
      )}
      {(modal === "consent" ||
        (me && !me.consented && path !== "/privacy")) && (
        <Modal
          title="Ваши данные — под вашим контролем"
          close={() => {
            setModal("");
            if (me && !me.consented && path !== "/privacy")
              run(async () => {
                await post("/auth/logout");
                setMe(null);
              });
          }}
        >
          <Consent
            busy={busy}
            onAccept={() =>
              run(async () => {
                await post("/consent", {
                  accepted: true,
                  version: config.privacy_version,
                });
                setModal("");
                await refresh();
                router.push("/profile");
              })
            }
          />
        </Modal>
      )}
      {modal === "record" && (
        <Modal title="Добавить данные" close={() => setModal("")}>
          <RecordForm
            busy={busy}
            onSave={(value) =>
              run(async () => {
                await post("/records", value);
                setModal("");
                await refresh();
                toast("Запись сохранена.");
              })
            }
          />
        </Modal>
      )}
      {modal === "review" && review && (
        <Modal
          title={review.extraction?.title || "Ваш документ"}
          close={() => setModal("")}
        >
          <DocumentReview
            document={review}
            profile={profile}
            busy={busy}
            onSave={(data) =>
              run(async () => {
                await post("/documents/" + review.id + "/confirm", data);
                setModal("");
                await refresh();
                toast("Проверенные данные сохранены.");
              })
            }
            onRetry={() =>
              run(async () => {
                await post("/documents/" + review.id + "/retry");
                setModal("");
                await refresh();
              })
            }
            onDelete={() =>
              run(async () => {
                await api("/documents/" + review.id, { method: "DELETE" });
                setModal("");
                await refresh();
              })
            }
          />
        </Modal>
      )}
      {modal === "link" && (
        <Modal title="Подключить Telegram" close={() => setModal("")}>
          <LinkTelegram
            onDone={async () => {
              setModal("");
              await refresh();
              toast("Telegram подключён. Теперь у вас одна история.");
            }}
            onError={toast}
          />
        </Modal>
      )}
      {modal === "delete" && (
        <Modal title="Удалить мои данные" close={() => setModal("")}>
          <DeleteAccount
            busy={busy}
            onDelete={() =>
              run(async () => {
                await api("/account", {
                  method: "DELETE",
                  body: JSON.stringify({ confirmation: "УДАЛИТЬ" }),
                });
                setMe(null);
                setDocuments([]);
                setMessages([]);
                setRecords([]);
                setModal("");
                router.push("/app");
              })
            }
          />
        </Modal>
      )}
      {modal === "history" && (
        <Modal title="История изменений профиля" close={() => setModal("")}>
          {review?.history?.length ? (
            review.history.map((h: Item) => (
              <details key={h.id}>
                <summary>
                  {formatDate(h.created_at)} ·{" "}
                  {h.data.source === "user"
                    ? "Изменено вами"
                    : "Подтверждено из документа"}
                </summary>
                <p>
                  {Object.keys(h.data.after)
                    .filter((k) => h.data.before?.[k] !== h.data.after[k])
                    .join(", ")}
                </p>
              </details>
            ))
          ) : (
            <p>Изменений пока нет.</p>
          )}
        </Modal>
      )}
      {modal === "notifications" && (
        <Modal title="Уведомления" close={() => setModal("")}>
          {notificationList.length ? (
            notificationList.map((n) => <p key={n.id}>{n.text}</p>)
          ) : (
            <Empty
              title="Пока всё спокойно"
              text="Здесь появятся напоминания и сообщения об обработке документов."
            />
          )}
        </Modal>
      )}
      {modal === "support-sent" && (
        <Modal title="Обращение отправлено" close={() => setModal("")}>
          <p>
            Ответ появится в разделе помощи. Спасибо, что рассказали о проблеме.
          </p>
          <Button onClick={() => setModal("")}>Понятно</Button>
        </Modal>
      )}
    </div>
  );
}

function PageTitle({
  eyebrow,
  title,
  text,
  action,
}: {
  eyebrow: string;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="welcome">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      {action}
    </div>
  );
}
function LabCharts({ records }: { records: Item[] }) {
  const titles = Array.from(
    new Set(records.filter((r) => r.kind === "lab").map((r) => r.title)),
  );
  const [selected, setSelected] = useState("");
  return (
    <>
      {titles.length > 0 && (
        <select
          value={selected || titles[0]}
          onChange={(e) => setSelected(e.target.value)}
          aria-label="Показатель"
        >
          {titles.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      )}
      <Chart
        records={records.filter((r) => r.title === (selected || titles[0]))}
        kind="lab"
      />
    </>
  );
}
function Login({
  config,
  onDone,
  onError,
}: {
  config: Item;
  onDone: () => void;
  onError: (s: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    async function init() {
      try {
        const { nonce } = await api("/auth/challenge");
        if (!active) return;
        window.google?.accounts.id.initialize({
          client_id: config.google_client_id,
          nonce,
          callback: async (r: Item) => {
            try {
              await post("/auth/google", { credential: r.credential });
              onDone();
            } catch (e) {
              onError((e as Error).message);
            }
          },
        });
        if (ref.current)
          window.google?.accounts.id.renderButton(ref.current, {
            theme: "outline",
            size: "large",
            width: 300,
            text: "continue_with",
            locale: "ru",
          });
      } catch (e) {
        onError((e as Error).message);
      }
    }
    if (window.google) init();
    else {
      const s = document.createElement("script");
      s.src = "https://accounts.google.com/gsi/client";
      s.onload = init;
      s.onerror = () =>
        onError("Google не загрузился. Попробуйте вход через Telegram.");
      document.head.appendChild(s);
    }
    return () => {
      active = false;
    };
  }, [config.google_client_id]);
  return (
    <div className="login-content">
      <img src="/logo.png" alt="Neyrix Mama" />
      <h3>Беременность. Понятно. Спокойно. Рядом.</h3>
      <p>
        Войдите, чтобы сохранить свою историю и настроить помощника под себя.
      </p>
      {config.google_client_id ? (
        <div className="google-login" ref={ref} />
      ) : (
        <p>Вход Google ещё не настроен.</p>
      )}
      <a
        className="button secondary"
        href={`https://t.me/${config.bot_username}`}
        target="_blank"
        rel="noreferrer"
      >
        <Send size={17} /> Продолжить в Telegram
      </a>
      <p className="fine-print">
        В боте выберите «Открыть приложение»: вход произойдёт автоматически.
      </p>
    </div>
  );
}
function Consent({ onAccept, busy }: { onAccept: () => void; busy: boolean }) {
  const [accepted, setAccepted] = useState(false);
  return (
    <>
      <p>
        Для ведения профиля приложение хранит сведения о беременности, документы
        и историю общения. При использовании AI нужные данные передаются
        настроенному провайдеру обработки.
      </p>
      <p>
        Вы можете скачать или удалить свои данные в профиле. Ассистент носит
        информационный характер и не заменяет врача.
      </p>
      <Link href="/privacy" target="_blank" className="text-button">
        Подробнее об обработке данных <ArrowUpRight size={16} />
      </Link>
      <label className="check-label">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
        />{" "}
        Я ознакомилась с условиями и согласна на обработку моих персональных
        данных и сведений о здоровье.
      </label>
      <Button disabled={!accepted || busy} onClick={onAccept}>
        Продолжить
      </Button>
    </>
  );
}
const profileSteps = [
  {
    title: "Немного о вас",
    fields: [
      ["name", "Как к вам обращаться?", "text"],
      ["age", "Возраст", "number"],
      ["height", "Рост, см", "number"],
      ["pre_weight", "Вес до беременности, кг", "number"],
      ["current_weight", "Текущий вес, кг", "number"],
    ],
  },
  {
    title: "Теперь о беременности",
    fields: [
      ["lmp", "Первый день последней менструации", "date"],
      ["due_date", "Предполагаемая дата родов", "date"],
      ["conception_date", "Дата зачатия, если известна", "date"],
      ["doctor_weeks", "Срок, установленный врачом: недель", "number"],
      ["doctor_days", "И дней", "number"],
      ["doctor_date", "На какую дату врач определил срок?", "date"],
      ["first_pregnancy", "Первая ли беременность?", "select"],
    ],
  },
  {
    title: "Ваш опыт",
    fields: [
      [
        "history",
        "Предыдущие беременности и роды, операции. Можно пропустить.",
        "textarea",
      ],
    ],
  },
  {
    title: "Здоровье",
    fields: [
      [
        "chronic",
        "Хронические заболевания, операции и ограничения",
        "textarea",
      ],
      ["allergies", "Аллергии", "text"],
      ["blood_group", "Группа крови, если знаете", "text"],
      ["rh", "Резус-фактор", "select"],
    ],
  },
  {
    title: "Физическая активность",
    fields: [
      ["activity", "Привычная активность", "select"],
      ["frequency", "Тренировок в неделю", "number"],
      ["training_history", "Опыт тренировок и ограничения", "textarea"],
      [
        "lifestyle",
        "Особенности питания и образа жизни (по желанию)",
        "textarea",
      ],
    ],
  },
  {
    title: "Лекарства и витамины",
    fields: [
      ["medications", "Назначенные лекарства и дозировки", "textarea"],
      ["supplements", "Витамины и добавки", "textarea"],
    ],
  },
];
function ProfileEditor({
  initial,
  busy,
  onSave,
}: {
  initial: Item;
  busy: boolean;
  onSave: (p: Item) => void;
}) {
  const [step, setStep] = useState(0),
    [value, setValue] = useState<Item>(initial);
  const group = profileSteps[step];
  const options: Item = {
    first_pregnancy: ["", "Да", "Нет", "Предпочитаю не отвечать"],
    rh: ["", "Положительный", "Отрицательный", "Не знаю"],
    activity: [
      "",
      "Не занималась",
      "Лёгкая активность",
      "Регулярные тренировки",
      "Силовые тренировки",
      "Кардио / бег",
      "Йога / пилатес",
      "Другое",
    ],
  };
  function save(e: FormEvent) {
    e.preventDefault();
    const data = { ...value };
    for (const g of profileSteps)
      for (const [key, , type] of g.fields) {
        if (type === "number")
          data[key] =
            data[key] === "" || data[key] === undefined
              ? null
              : Number(data[key]);
        if (type === "date" && !data[key]) data[key] = null;
      }
    onSave({ ...data, completed: step === 5 || value.completed });
  }
  return (
    <form className="card profile-editor" onSubmit={save}>
      <div className="step-header">
        <span className="pill mint">Шаг {step + 1} из 6</span>
        <span className="muted">Данные можно изменить в любой момент</span>
      </div>
      <div className="step-progress">
        {profileSteps.map((s, i) => (
          <button
            type="button"
            key={i}
            aria-label={s.title}
            className={i <= step ? "filled" : ""}
            onClick={() => setStep(i)}
          />
        ))}
      </div>
      <h2>{group.title}</h2>
      <div className="form-grid">
        {group.fields.map(([key, label, type]) => (
          <label className={type === "textarea" ? "full-width" : ""} key={key}>
            {label}
            {type === "textarea" ? (
              <textarea
                value={value[key] || ""}
                maxLength={3000}
                onChange={(e) => setValue({ ...value, [key]: e.target.value })}
              />
            ) : type === "select" ? (
              <select
                value={value[key] || ""}
                onChange={(e) => setValue({ ...value, [key]: e.target.value })}
              >
                {options[key].map((s: string) => (
                  <option key={s} value={s}>
                    {s || "Не указано"}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={type}
                step={type === "number" ? "any" : undefined}
                value={value[key] ?? ""}
                onChange={(e) => setValue({ ...value, [key]: e.target.value })}
              />
            )}
          </label>
        ))}
      </div>
      <div className="form-actions">
        <Button
          secondary
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
        >
          <ChevronLeft size={16} /> Назад
        </Button>
        <Button disabled={busy} type="submit">
          <Check size={16} /> Сохранить
        </Button>
        {step < 5 ? (
          <Button secondary onClick={() => setStep(step + 1)}>
            Далее <ArrowRight size={16} />
          </Button>
        ) : (
          <Link href="/app" className="text-button">
            В приложение <ArrowRight size={16} />
          </Link>
        )}
      </div>
    </form>
  );
}
function RecordForm({
  busy,
  onSave,
}: {
  busy: boolean;
  onSave: (p: Item) => void;
}) {
  const [kind, setKind] = useState("weight");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.currentTarget));
        onSave({
          ...data,
          kind,
          recorded_at: new Date(data.recorded_at + "T12:00:00").toISOString(),
          value: data.value ? Number(data.value) : null,
          secondary: data.secondary ? Number(data.secondary) : null,
        });
      }}
    >
      <label>
        Что добавим?
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {Object.entries(labels).map(([v, t]) => (
            <option key={v} value={v}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <div className="form-grid">
        <label>
          Дата
          <input
            name="recorded_at"
            type="date"
            required
            defaultValue={dateInput()}
          />
        </label>
        <label>
          Название
          <input name="title" placeholder={labels[kind]} maxLength={200} />
        </label>
        {["weight", "blood_pressure", "lab", "ultrasound"].includes(kind) && (
          <>
            <label>
              {kind === "blood_pressure" ? "Верхнее давление" : "Значение"}
              <input name="value" type="number" step="any" required />
            </label>
            {kind === "blood_pressure" ? (
              <label>
                Нижнее давление
                <input name="secondary" type="number" required />
              </label>
            ) : (
              <label>
                Единицы
                <input
                  name="unit"
                  defaultValue={kind === "weight" ? "кг" : ""}
                />
              </label>
            )}
          </>
        )}
        <label className="full-width">
          Заметка
          <textarea
            name="notes"
            placeholder="Что важно сохранить?"
            maxLength={5000}
          />
        </label>
      </div>
      <Button type="submit" disabled={busy}>
        <Check size={17} /> Сохранить запись
      </Button>
    </form>
  );
}
function DocumentReview({
  document: d,
  profile,
  busy,
  onSave,
  onRetry,
  onDelete,
}: {
  document: Item;
  profile: Item;
  busy: boolean;
  onSave: (v: Item) => void;
  onRetry: () => void;
  onDelete: () => void;
}) {
  const ex = d.extraction || {};
  const [items, setItems] = useState<Item[]>(
      (ex.values || []).map((v: Item) => ({
        ...v,
        kind: v.kind === "ultrasound" ? "ultrasound" : "lab",
      })),
    ),
    [date, setDate] = useState(ex.date || ""),
    [update, setUpdate] = useState(false),
    [confirmDelete, setConfirmDelete] = useState(false);
  return (
    <>
      <p>
        {d.name} · <b>{statusLabels[d.status]}</b>
      </p>
      <a className="text-button" href={"/api/documents/" + d.id + "/download"}>
        <Download size={17} /> Скачать оригинал
      </a>
      {d.status === "failed" && (
        <div className="info-box">
          {ex.error || "Не получилось обработать файл."}
          <Button secondary disabled={busy} onClick={onRetry}>
            Повторить обработку
          </Button>
        </div>
      )}
      {["queued", "processing"].includes(d.status) && (
        <p>Документ обрабатывается. Результат появится в списке.</p>
      )}
      {d.status === "review" && (
        <>
          <div className="info-box">
            Проверьте каждое значение по оригиналу. Распознавание может
            ошибаться. Медицинские данные сохранятся только после вашего
            подтверждения.
          </div>
          <label>
            Дата исследования
            <input
              type="date"
              required
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
          {items.map((v, i) => (
            <div className="review-item" key={i}>
              <input
                aria-label="Название показателя"
                value={v.title || ""}
                onChange={(e) =>
                  setItems(
                    items.map((x, j) =>
                      j === i ? { ...x, title: e.target.value } : x,
                    ),
                  )
                }
              />
              <input
                aria-label="Значение показателя"
                type="number"
                step="any"
                value={v.value ?? ""}
                onChange={(e) =>
                  setItems(
                    items.map((x, j) =>
                      j === i
                        ? {
                            ...x,
                            value:
                              e.target.value === ""
                                ? null
                                : Number(e.target.value),
                          }
                        : x,
                    ),
                  )
                }
              />
              <input
                aria-label="Единицы измерения"
                value={v.unit || ""}
                onChange={(e) =>
                  setItems(
                    items.map((x, j) =>
                      j === i ? { ...x, unit: e.target.value } : x,
                    ),
                  )
                }
              />
              <button
                className="icon-button"
                aria-label="Убрать показатель"
                onClick={() => setItems(items.filter((_, j) => j !== i))}
              >
                <X size={16} />
              </button>
              {(v.confidence || 0) < 0.85 && (
                <small className="review-warning">
                  Не удалось уверенно прочитать. Проверьте по оригиналу.
                </small>
              )}
            </div>
          ))}
          <Button
            secondary
            onClick={() =>
              setItems([
                ...items,
                { kind: "lab", title: "", value: null, unit: "" },
              ])
            }
          >
            <Plus size={16} /> Показатель
          </Button>
          {ex.conclusion && <p>{ex.conclusion}</p>}
          {ex.gestation_proposal && (
            <div className="info-box">
              <b>Мы нашли другие данные о сроке беременности</b>
              <p>
                По документу от{" "}
                {formatDate(ex.gestation_proposal.document_date)} сейчас{" "}
                {ex.gestation_proposal.weeks} недель{" "}
                {ex.gestation_proposal.days} дней. Данные профиля пока не
                изменены.
              </p>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={update}
                  onChange={(e) => setUpdate(e.target.checked)}
                />{" "}
                Подтверждаю обновление срока по этому документу
              </label>
            </div>
          )}
          <div className="form-actions">
            <Button
              disabled={
                busy || !date || items.some((x) => x.value === null || !x.title)
              }
              onClick={() =>
                onSave({
                  records: items.map((v) => ({
                    kind: v.kind,
                    title: v.title,
                    value: v.value,
                    unit: v.unit || "",
                    reference: v.reference || "",
                    recorded_at: new Date(date + "T12:00:00").toISOString(),
                  })),
                  profile_update: update
                    ? {
                        ...profile,
                        doctor_weeks: ex.gestational_weeks,
                        doctor_days: ex.gestational_days || 0,
                        doctor_date: ex.date,
                      }
                    : null,
                })
              }
            >
              <Check size={16} /> Подтвердить и сохранить
            </Button>
          </div>
        </>
      )}
      {d.status === "confirmed" && (
        <div className="info-box">
          <CheckCircle2 size={18} /> Данные проверены и сохранены.
          Подтверждённые показатели доступны в разделе динамики.
        </div>
      )}
      <hr />
      {confirmDelete ? (
        <div className="button-row">
          <p>Удалить оригинал документа? Сохранённые показатели останутся.</p>
          <Button disabled={busy} onClick={onDelete}>
            Да, удалить документ
          </Button>
        </div>
      ) : (
        <button className="danger-link" onClick={() => setConfirmDelete(true)}>
          Удалить документ
        </button>
      )}
    </>
  );
}
function LinkTelegram({
  onDone,
  onError,
}: {
  onDone: () => void;
  onError: (s: string) => void;
}) {
  const [url, setUrl] = useState(""),
    [subject, setSubject] = useState("");
  async function create() {
    try {
      setUrl((await post("/link/telegram")).url);
    } catch (e) {
      onError((e as Error).message);
    }
  }
  async function check() {
    try {
      const r = await api("/link/telegram");
      setSubject(r.telegram_id || "");
      if (!r.telegram_id)
        onError("Сначала откройте ссылку и подтвердите действие в боте.");
    } catch (e) {
      onError((e as Error).message);
    }
  }
  async function confirm() {
    try {
      await post("/link/telegram/confirm", { telegram_id: subject });
      onDone();
    } catch (e) {
      onError((e as Error).message);
    }
  }
  return (
    <>
      <p>
        Сначала откройте бота по одноразовой ссылке. Затем вернитесь сюда и
        подтвердите, что Telegram ID принадлежит вам. Ссылка действует 10 минут.
      </p>
      {!url ? (
        <Button onClick={create}>Создать ссылку</Button>
      ) : (
        <div className="button-row">
          <a
            className="button primary"
            href={url}
            target="_blank"
            rel="noreferrer"
          >
            Открыть Telegram <ArrowUpRight size={16} />
          </a>
          <Button secondary onClick={check}>
            Я вернулась из Telegram
          </Button>
        </div>
      )}
      {subject && (
        <div className="info-box">
          <p>
            Подключить Telegram ID <b>{subject}</b> к вашему профилю?
          </p>
          <Button onClick={confirm}>Это мой аккаунт — подключить</Button>
        </div>
      )}
    </>
  );
}
function DeleteAccount({
  onDelete,
  busy,
}: {
  onDelete: () => void;
  busy: boolean;
}) {
  const [text, setText] = useState("");
  return (
    <>
      <p>
        Профиль, документы, показатели и история общения будут удалены.
        Автопродление остановится. Это действие нельзя отменить. Заранее
        скачайте нужные данные.
      </p>
      <label>
        Введите УДАЛИТЬ
        <input value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      <Button disabled={text !== "УДАЛИТЬ" || busy} onClick={onDelete}>
        <Trash2 size={16} /> Удалить аккаунт
      </Button>
    </>
  );
}
function SubscriptionPanel({
  demo,
  config,
  subscription,
  busy,
  onStart,
  onCancel,
}: {
  demo: boolean;
  config: Item;
  subscription?: Item;
  busy: boolean;
  onStart: (b: boolean) => void;
  onCancel: () => void;
}) {
  const [renew, setRenew] = useState(false);
  return (
    <div className="subscription-layout">
      <section className="card plan">
        <span className="pill mint">Первый месяц бесплатно</span>
        <h2>Neyrix Mama</h2>
        <p>От первых недель до встречи с малышом</p>
        <div className="price">
          {config.price} ₽ <span>/ месяц</span>
        </div>
        {[
          "Персональный AI-ассистент",
          "Анализы и УЗИ в одном месте",
          "Распознавание с вашим подтверждением",
          "Динамика показателей",
          "Единый профиль в Telegram и Web",
          "Напоминания и подготовка к врачу",
        ].map((s) => (
          <div className="plan-feature" key={s}>
            <CheckCircle2 size={18} />
            {s}
          </div>
        ))}
        <label className="check-label">
          <input
            type="checkbox"
            checked={renew}
            onChange={(e) => setRenew(e.target.checked)}
          />{" "}
          Согласна на ежемесячное автопродление за {config.price} ₽. Его можно
          отключить в любой момент.
        </label>
        <Button disabled={busy} onClick={() => onStart(renew)}>
          {demo ? "Начать бесплатно" : `Продолжить за ${config.price} ₽/мес`}
          <ArrowRight size={17} />
        </Button>
        <p className="fine-print">
          Ваши данные остаются доступны после окончания подписки.
        </p>
      </section>
      <section className="card subscription-info">
        <Heart className="teal" size={30} />
        <h2>Забота без давления</h2>
        <p>
          Подписка открывает общение с ассистентом и расширенные возможности.
          Доступ к вашим сохранённым данным остаётся у вас.
        </p>
        {!demo && (
          <>
            <hr />
            <h3>Ваша подписка</h3>
            <p>
              Статус:{" "}
              {
                (
                  {
                    trialing: "Бесплатный месяц",
                    active: "Активна",
                    cancelled: "Автопродление отключено",
                    expired: "Период завершён",
                    past_due: "Ожидает оплаты",
                  } as Item
                )[subscription?.status || ""]
              }
            </p>
            <p>
              До{" "}
              {subscription?.ends_at ? formatDate(subscription.ends_at) : "—"}
            </p>
            <p>
              Вопросов сегодня: {subscription?.remaining} из{" "}
              {subscription?.limit}
            </p>
            <p>Лимит обновляется в 00:00 по Москве.</p>
            {subscription?.auto_renew && (
              <Button secondary disabled={busy} onClick={onCancel}>
                Отключить автопродление
              </Button>
            )}
          </>
        )}
      </section>
    </div>
  );
}
function SupportPanel({
  demo,
  busy,
  send,
}: {
  demo: boolean;
  busy: boolean;
  send: (x: Item) => void;
}) {
  const [tickets, setTickets] = useState<Item[]>([]);
  useEffect(() => {
    if (!demo)
      api("/support")
        .then(setTickets)
        .catch(() => {});
  }, [demo, busy]);
  return (
    <div className="support-grid">
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          send(Object.fromEntries(new FormData(e.currentTarget)));
        }}
      >
        <h2>Написать в поддержку</h2>
        <label>
          Тема
          <select name="category">
            {[
              "Проблема с оплатой",
              "Не загрузился анализ",
              "Проблема со входом",
              "Ошибка данных",
              "Другое",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Что произошло?
          <textarea
            name="text"
            required
            minLength={3}
            maxLength={5000}
            placeholder="Опишите ситуацию. Не присылайте пароли и данные банковской карты."
          />
        </label>
        <Button disabled={busy} type="submit">
          <Send size={17} /> Отправить
        </Button>
      </form>
      <div className="card">
        <h2>Ваши обращения</h2>
        {tickets.length ? (
          tickets.map((t) => (
            <div className="ticket" key={t.id}>
              <h3>{t.category}</h3>
              <p>{t.text}</p>
              <small>
                {t.status === "open" ? "Ожидает ответа" : "Ответ получен"}
              </small>
              {t.reply && <div className="info-box">{t.reply}</div>}
            </div>
          ))
        ) : (
          <p>Здесь появятся обращения и ответы команды.</p>
        )}
        <hr />
        <h3>Если нужна срочная медицинская помощь</h3>
        <p>
          Поддержка не оказывает медицинскую помощь. При экстренных симптомах
          звоните <a href="tel:112">112</a> или <a href="tel:103">103</a>.
        </p>
      </div>
    </div>
  );
}
function Privacy() {
  return (
    <article className="card legal">
      <h1>Обработка ваших данных</h1>
      <p>
        Приложение хранит профиль беременности, документы, показатели, историю
        общения, настройки подписки и обращения в поддержку. Вход связывается с
        идентификатором Google или Telegram.
      </p>
      <h2>Как используются данные</h2>
      <p>
        Для ответа ассистенту передаются релевантные сведения профиля,
        показатели и история. Документы передаются провайдеру распознавания по
        вашему запросу. Реквизиты банковской карты обрабатывает платёжный
        провайдер; приложение их не хранит.
      </p>
      <h2>Ваш контроль</h2>
      <p>
        В профиле можно скачать данные, отключить уведомления и удалить аккаунт.
        После удаления информация в резервных копиях исчезает в пределах
        установленного оператором срока хранения. Доступ администратора к
        профилям фиксируется в журнале.
      </p>
      <h2>Статус документа</h2>
      <p>
        Это проект условий для тестовой версии. До публичного запуска владелец
        сервиса должен указать юридическое лицо и контакты оператора, выбранных
        обработчиков и страны обработки, основания и сроки хранения, порядок
        отзыва согласия и утвердить окончательный текст. Не загружайте реальные
        медицинские документы в публичную тестовую установку до публикации этих
        сведений.
      </p>
    </article>
  );
}
function AdminPanel({ onError }: { onError: (s: string) => void }) {
  const [tab, setTab] = useState("overview"),
    [loaded, setLoaded] = useState(false),
    [denied, setDenied] = useState(false),
    [stats, setStats] = useState<Item>({}),
    [cfg, setCfg] = useState<Item>({}),
    [users, setUsers] = useState<Item[]>([]),
    [kb, setKb] = useState<Item[]>([]),
    [support, setSupport] = useState<Item[]>([]),
    [audit, setAudit] = useState<Item[]>([]),
    [query, setQuery] = useState(""),
    [detail, setDetail] = useState<Item | null>(null);
  async function load() {
    try {
      const r = await api("/admin/overview");
      setStats(r);
      const [c, u, k, s, a] = await Promise.all([
        api("/admin/config"),
        api("/admin/users?q=" + encodeURIComponent(query)),
        api("/admin/knowledge"),
        api("/admin/support"),
        api("/admin/audit"),
      ]);
      setCfg(c);
      setUsers(u);
      setKb(k);
      setSupport(s);
      setAudit(a);
      setLoaded(true);
    } catch (e) {
      setDenied(true);
      onError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function action(fn: () => Promise<any>) {
    try {
      await fn();
      await load();
      onError("Изменения сохранены.");
    } catch (e) {
      onError((e as Error).message);
    }
  }
  if (denied)
    return (
      <Empty
        title="Доступ только для администратора"
        text="Войдите через разрешённый Google-аккаунт. Права назначаются владельцем сервиса."
      />
    );
  if (!loaded) return <LoaderCircle className="spin" />;
  return (
    <>
      <PageTitle
        eyebrow="УПРАВЛЕНИЕ СЕРВИСОМ"
        title="Neyrix Mama Admin"
        text="Настройки применяются без повторного развёртывания."
      />
      <div className="tabs">
        {[
          ["overview", "Обзор"],
          ["users", "Пользователи"],
          ["config", "AI и подписка"],
          ["knowledge", "База знаний"],
          ["support", "Обращения"],
          ["audit", "Журнал"],
        ].map(([v, t]) => (
          <button
            key={v}
            className={tab === v ? "active" : ""}
            onClick={() => setTab(v)}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "overview" && (
        <div className="metric-grid">
          {Object.entries(stats).map(([k, v]) => (
            <div className="card metric" key={k}>
              <span>
                {
                  (
                    {
                      users: "Пользователи",
                      documents: "Документы",
                      questions: "AI-вопросы",
                      errors: "Ошибки обработки",
                      paid: "Платные",
                      trial: "Пробный период",
                      new_week: "Новые за неделю",
                    } as Item
                  )[k]
                }
              </span>
              <strong>{v}</strong>
            </div>
          ))}
        </div>
      )}
      {tab === "users" && (
        <div className="card">
          <form
            className="button-row"
            onSubmit={(e) => {
              e.preventDefault();
              action(async () =>
                setUsers(
                  await api("/admin/users?q=" + encodeURIComponent(query)),
                ),
              );
            }}
          >
            <input
              aria-label="Поиск пользователя"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Email, Telegram ID или имя"
            />
            <Button type="submit">
              <Search size={17} /> Найти
            </Button>
          </form>
          {users.map((u) => (
            <div className="admin-user" key={u.id}>
              <div>
                <h3>{u.name || "Без имени"}</h3>
                <small>{u.id}</small>
                <p>
                  {u.identities
                    .map((i: Item) => i.email || i.subject)
                    .join(" · ")}
                </p>
                <span className="pill neutral">{u.subscription.status}</span>
              </div>
              <div className="button-row">
                <Button
                  secondary
                  onClick={() =>
                    action(async () =>
                      setDetail(await api("/admin/users/" + u.id)),
                    )
                  }
                >
                  Профиль
                </Button>
                {[1, 3, 9].map((n) => (
                  <Button
                    secondary
                    key={n}
                    onClick={() =>
                      action(() =>
                        api("/admin/users/" + u.id, {
                          method: "PATCH",
                          body: JSON.stringify({ months: n }),
                        }),
                      )
                    }
                  >
                    +{n} мес.
                  </Button>
                ))}
                <Button
                  secondary
                  onClick={() =>
                    action(() =>
                      api("/admin/users/" + u.id, {
                        method: "PATCH",
                        body: JSON.stringify({ blocked: !u.blocked }),
                      }),
                    )
                  }
                >
                  {u.blocked ? "Разблокировать" : "Заблокировать"}
                </Button>
                <label>
                  Лимит в сутки
                  <input
                    type="number"
                    defaultValue={u.subscription.limit}
                    min="0"
                    max="1000"
                    onBlur={(e) => {
                      if (Number(e.target.value) !== u.subscription.limit)
                        action(() =>
                          api("/admin/users/" + u.id, {
                            method: "PATCH",
                            body: JSON.stringify({
                              daily_limit: Number(e.target.value),
                            }),
                          }),
                        );
                    }}
                  />
                </label>
                <Button
                  secondary
                  onClick={() =>
                    action(() =>
                      api("/admin/users/" + u.id, {
                        method: "PATCH",
                        body: JSON.stringify({ cancel: true }),
                      }),
                    )
                  }
                >
                  Отключить продление
                </Button>
              </div>
            </div>
          ))}
          {detail && (
            <Modal title="Профиль пользователя" close={() => setDetail(null)}>
              <dl>
                {Object.entries(detail.profile).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{String(v ?? "—")}</dd>
                  </div>
                ))}
              </dl>
            </Modal>
          )}
        </div>
      )}
      {tab === "config" && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            action(() => put("/admin/config", cfg));
          }}
        >
          <div className="form-grid">
            {[
              ["price", "Цена, ₽"],
              ["trial_days", "Дней бесплатно"],
              ["trial_limit", "Вопросов в trial"],
              ["paid_limit", "Вопросов в подписке"],
              ["max_tokens", "Максимум токенов"],
              ["temperature", "Температура"],
              ["timeout", "Таймаут, сек."],
              ["model", "Основная модель"],
              ["fallback_model", "Резервная модель"],
              ["vision_model", "Модель распознавания"],
            ].map(([k, label]) => (
              <label key={k}>
                {label}
                <input
                  type={k.includes("model") ? "text" : "number"}
                  step="any"
                  value={cfg[k] ?? ""}
                  onChange={(e) =>
                    setCfg({
                      ...cfg,
                      [k]: k.includes("model")
                        ? e.target.value
                        : Number(e.target.value),
                    })
                  }
                />
              </label>
            ))}
          </div>
          <label>
            Системный промпт
            <textarea
              className="prompt-editor"
              value={cfg.system_prompt || ""}
              onChange={(e) =>
                setCfg({ ...cfg, system_prompt: e.target.value })
              }
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={cfg.features?.maintenance || false}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  features: { ...cfg.features, maintenance: e.target.checked },
                })
              }
            />{" "}
            Приостановить новые AI-запросы
          </label>
          <Button type="submit">Сохранить настройки</Button>
        </form>
      )}
      {tab === "knowledge" && (
        <div className="card">
          <h2>Версии базы знаний</h2>
          <p>
            Загрузите новую версию, дождитесь индексации и выключите предыдущую.
          </p>
          <input
            type="file"
            accept=".md,.txt,.pdf,.docx"
            onChange={(e) => {
              if (e.target.files?.[0]) {
                const f = new FormData();
                f.append("file", e.target.files[0]);
                action(() =>
                  api("/admin/knowledge", { method: "POST", body: f }),
                );
              }
            }}
          />
          {kb.map((k) => (
            <div className="document-row" key={k.id}>
              <div>
                <b>{k.name}</b>
                <p>
                  {k.status} · {Math.round(k.size / 1024)} КБ
                </p>
              </div>
              <Button
                secondary
                onClick={() =>
                  action(() =>
                    api("/admin/knowledge/" + k.id, {
                      method: "PATCH",
                      body: JSON.stringify({ enabled: !k.enabled }),
                    }),
                  )
                }
              >
                {k.enabled ? "Выключить" : "Включить"}
              </Button>
              <Button
                secondary
                onClick={() => {
                  if (window.confirm("Удалить эту версию базы знаний?"))
                    action(() =>
                      api("/admin/knowledge/" + k.id, { method: "DELETE" }),
                    );
                }}
              >
                Удалить
              </Button>
            </div>
          ))}
        </div>
      )}
      {tab === "support" && (
        <div className="card">
          {support.map((s) => (
            <form
              className="ticket"
              key={s.id}
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                action(() =>
                  api("/admin/support/" + s.id, {
                    method: "PATCH",
                    body: JSON.stringify({ reply: f.get("reply") }),
                  }),
                );
              }}
            >
              <h3>{s.category}</h3>
              <p>{s.text}</p>
              <textarea
                name="reply"
                aria-label="Ответ поддержки"
                defaultValue={s.reply || ""}
              />
              <Button type="submit">Сохранить ответ</Button>
            </form>
          ))}
        </div>
      )}
      {tab === "audit" && (
        <div className="card audit">
          {audit.map((a) => (
            <p key={a.id}>
              <small>{formatDate(a.created_at)}</small> <b>{a.action}</b>{" "}
              {a.target}
            </p>
          ))}
        </div>
      )}
    </>
  );
}
