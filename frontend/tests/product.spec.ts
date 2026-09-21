import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
const root = path.resolve(__dirname, "../..");
const fixture = (id?: string) =>
  execFileSync(
    path.join(root, ".venv/bin/python"),
    ["-m", "tests.browser_user", ...(id ? [id] : [])],
    {
      cwd: path.join(root, "backend"),
      env: {
        ...process.env,
        DATABASE_URL: "sqlite:///" + path.join(root, "backend/dev.db"),
        PYTHONPATH: path.join(root, "backend"),
        STORAGE_DIR: path.join(root, "storage"),
      },
      encoding: "utf8",
    },
  );

test("demo dashboard, mobile layout and navigation", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/app");
  await expect(
    page.getByRole("heading", { name: /Добрый день, Анна/ }),
  ).toBeVisible();
  await expect(
    page.getByText("Это пример вашей будущей истории.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Вопрос ассистенту" })
    .pressSequentially("Как подготовиться к приёму?");
  await expect(
    page.getByRole("textbox", { name: "Вопрос ассистенту" }),
  ).toHaveValue("Как подготовиться к приёму?");
  await page.getByRole("button", { name: "Отправить вопрос" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("input[hidden]")).toBeHidden();
  expect(
    await page
      .locator(".main-shell")
      .evaluate((el) => el.getBoundingClientRect().width),
  ).toBeGreaterThan(380);
  for (const route of [
    "/app",
    "/data",
    "/chat",
    "/profile",
    "/subscription",
    "/support",
    "/dynamics",
  ]) {
    await page.goto(route);
    await expect(page.locator("h1").first()).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  }
  expect(errors).toEqual([]);
});

test("authenticated profile, measurement, upload, confirmation and AI history", async ({
  page,
  context,
}) => {
  const user = JSON.parse(fixture());
  try {
    await context.addCookies([
      {
        name: "mama_session",
        value: user.token,
        domain: "localhost",
        path: "/",
      },
    ]);
    await page.goto("/app");
    await expect(
      page.getByRole("heading", { name: /Проверка интерфейса/ }),
    ).toBeVisible();
    await expect(
      page.getByText("Это пример вашей будущей истории.", { exact: false }),
    ).toHaveCount(0);
    await page
      .getByRole("button", { name: "Добавить данные", exact: true })
      .click();
    await page.getByLabel("Значение", { exact: true }).fill("62.5");
    await page.getByRole("button", { name: "Сохранить запись" }).click();
    await expect(
      page.getByText("62.5", { exact: false }).first(),
    ).toBeVisible();
    await page.goto("/data");
    await expect(
      page.getByRole("button", { name: "Добавить документ", exact: true }),
    ).toBeVisible();
    await page
      .locator("input[type=file]")
      .first()
      .setInputFiles({
        name: "browser-test.txt",
        mimeType: "text/plain",
        buffer: Buffer.from(
          "Общий анализ крови. Гемоглобин 118 г/л. 18.09.2026",
        ),
      });
    await expect(
      page.getByRole("button", { name: /Общий анализ крови \(тест\)/ }),
    ).toBeVisible({ timeout: 30000 });
    await page
      .getByRole("button", { name: /Общий анализ крови \(тест\)/ })
      .click();
    await expect(page.getByLabel("Значение показателя")).toHaveValue("118");
    await page.getByRole("button", { name: "Подтвердить и сохранить" }).click();
    await expect(page.getByText("Гемоглобин", { exact: true })).toBeVisible();
    await page.goto("/chat");
    await page
      .getByRole("textbox", { name: "Вопрос ассистенту" })
      .fill("Как подготовиться к приёму?");
    await page.getByRole("button", { name: "Отправить вопрос" }).click();
    await expect(
      page.getByText("Тестовый ответ провайдера:", { exact: false }),
    ).toBeVisible({ timeout: 30000 });
    await page.reload();
    await expect(
      page.getByText("Тестовый ответ провайдера:", { exact: false }),
    ).toBeVisible();
  } finally {
    fixture(user.id);
  }
});
