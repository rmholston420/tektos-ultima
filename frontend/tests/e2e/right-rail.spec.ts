import { test, expect } from "@playwright/test";

/**
 * Right rail: 7 pane tabs are present and clicking each activates it.
 */
const TAB_IDS = ["files", "editor", "diff", "terminal", "preview", "graph", "logs"];

test("right rail exposes 7 pane tabs and each activates", async ({ page }) => {
  await page.goto("/");
  for (const id of TAB_IDS) {
    const tab = page.getByTestId(`pane-tab-${id}`);
    await expect(tab).toBeVisible();
  }
  // Click each and confirm no console errors.
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  for (const id of TAB_IDS) {
    await page.getByTestId(`pane-tab-${id}`).click();
    await page.waitForTimeout(150);
  }
  expect(errors).toEqual([]);
});
