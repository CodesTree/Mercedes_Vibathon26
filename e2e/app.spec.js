import { expect, test } from "@playwright/test";


test("loads frontend and displays backend data", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /React frontend/i })).toBeVisible();
  await expect(page.getByText("ok")).toBeVisible();
  await expect(page.getByText("Connect the frontend to FastAPI")).toBeVisible();
});
