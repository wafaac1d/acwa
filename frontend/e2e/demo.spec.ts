import { expect, test } from "@playwright/test";

test("demo campaign can be generated, approved and mock-published", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Пароль").fill(process.env.ACWA_AUTH_TOKEN ?? "");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Демонстрационный режим")).toBeVisible();
  await page.getByRole("link", { name: "Настройки" }).click();
  await page.getByRole("button", { name: "Подключить демонстрационный аккаунт" }).click();
  await expect(page.getByText("Демонстрационный аккаунт", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Кампании" }).click();
  await page.getByRole("link", { name: "Новая кампания" }).click();
  await expect(page.getByRole("combobox", { name: "Аккаунт" })).not.toHaveValue("");
  await page.getByLabel("Название").fill("E2E демонстрация");
  await page.getByLabel("Тема").fill("Проверка пробного поста");
  await page.getByRole("button", { name: "Сохранить" }).click();
  await page.getByRole("button", { name: "Сгенерировать" }).click();
  await expect(page.getByText("Ждёт одобрения")).toBeVisible({ timeout: 20_000 });
  await page.getByLabel("Текст поста").fill("Проверенный демонстрационный текст для e2e.");
  await page.getByRole("button", { name: "Сохранить текст" }).click();
  await page.getByRole("button", { name: "Одобрить" }).click();
  await expect(page.getByText("Опубликован")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Демо, в Threads не отправлено")).toBeVisible();
  await expect(page.getByText("Ссылки на Threads нет")).toBeVisible();
});
