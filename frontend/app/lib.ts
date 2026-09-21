export type Item = Record<string, any>;
export async function api(path: string, options: RequestInit = {}) {
  const response = await fetch("/api" + path, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  const result = await response
    .json()
    .catch(() => ({ detail: "Сервис временно недоступен." }));
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Проверьте введённые данные.",
    );
  return result;
}
export const post = (path: string, data: unknown = {}) =>
  api(path, { method: "POST", body: JSON.stringify(data) });
export const put = (path: string, data: unknown) =>
  api(path, { method: "PUT", body: JSON.stringify(data) });
export const formatDate = (value: string) =>
  new Date(value).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
  });
const ago = (days: number) =>
  new Date(Date.now() - days * 86400000).toISOString();
export const demoProfile: Item = {
  name: "Анна",
  age: 29,
  height: 168,
  pre_weight: 58,
  current_weight: 62.4,
  lmp: ago(130).slice(0, 10),
  completed: true,
  activity: "Йога / пилатес",
  frequency: 2,
};
export const demoRecords: Item[] = [
  ...[
    [28, 60.1],
    [21, 60.8],
    [14, 61.3],
    [7, 61.9],
    [0, 62.4],
  ].map(([days, value], i) => ({
    id: "weight-" + i,
    kind: "weight",
    title: "Вес",
    value,
    unit: "кг",
    recorded_at: ago(days),
    provenance: { source: "demo" },
  })),
  {
    id: "bp",
    kind: "blood_pressure",
    title: "Давление",
    value: 112,
    secondary: 72,
    unit: "мм рт. ст.",
    recorded_at: ago(1),
  },
  {
    id: "hb",
    kind: "lab",
    title: "Гемоглобин",
    value: 118,
    unit: "г/л",
    recorded_at: ago(3),
  },
  {
    id: "event",
    kind: "event",
    title: "Второй скрининг",
    notes: "Уточнить время и подготовку у врача",
    recorded_at: ago(-9),
  },
  {
    id: "ultra",
    kind: "ultrasound",
    title: "Плановое УЗИ",
    notes: "Пример записи о проведённом исследовании",
    recorded_at: ago(10),
  },
];
export const demoDocuments: Item[] = [
  {
    id: "d1",
    name: "Общий анализ крови.pdf",
    status: "confirmed",
    created_at: ago(3),
    size: 240000,
    extraction: { title: "Общий анализ крови" },
  },
  {
    id: "d2",
    name: "УЗИ второго триместра.jpg",
    status: "confirmed",
    created_at: ago(10),
    size: 1800000,
    extraction: { title: "Ультразвуковое исследование" },
  },
];
export const demoChat: Item[] = [
  {
    id: "a",
    role: "assistant",
    text: "Здравствуйте, Анна! Здесь можно обсудить анализы, подготовиться к приёму или задать вопрос о беременности. Это пример чата — для персональных ответов создайте свой профиль.",
  },
];
export const labels: Item = {
  weight: "Вес",
  blood_pressure: "Давление",
  lab: "Анализ",
  ultrasound: "УЗИ",
  medication: "Лекарство",
  supplement: "Витамины",
  symptom: "Самочувствие",
  activity: "Тренировка",
  event: "Событие",
  note: "Заметка",
};
export const statusLabels: Item = {
  queued: "В очереди",
  processing: "Обрабатываем",
  review: "Проверьте данные",
  confirmed: "Данные сохранены",
  failed: "Нужна повторная обработка",
};
export async function pollTask(
  id: string,
  onUpdate?: (status: string) => void,
): Promise<Item> {
  for (let i = 0; i < 180; i++) {
    const task = await api("/tasks/" + id);
    onUpdate?.(task.status);
    if (task.status === "done") return task.result;
    if (task.status === "failed")
      throw new Error(task.result.error + " Код: " + task.id.slice(0, 8));
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error(
    "Обработка продолжается. Результат появится в истории — вернитесь чуть позже.",
  );
}
