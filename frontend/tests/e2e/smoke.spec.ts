import { test, expect } from "@playwright/test";

test("home renders shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Chat")).toBeVisible();
  await expect(page.getByLabel("Navigation")).toBeVisible();
  await expect(page.getByLabel("Contextual pane")).toBeVisible();
});
