import { test, expect } from "@playwright/test";

/**
 * Command palette e2e: \u2318K opens the palette, typing filters, Enter
 * fires the action.
 */
test("cmd+k opens the palette and navigates", async ({ page }) => {
  await page.goto("/");
  const isMac = process.platform === "darwin";
  const modifier = isMac ? "Meta" : "Control";
  await page.keyboard.press(`${modifier}+KeyK`);
  await expect(page.getByTestId("command-palette-overlay")).toBeVisible();

  // Type to filter to a nav command.
  await page.keyboard.type("Artifacts");
  await page.keyboard.press("Enter");

  // We should have navigated to the /artifacts destination.
  await expect(page).toHaveURL(/\/artifacts$/);
  await expect(page.getByRole("heading", { name: /Artifacts/i })).toBeVisible();
});
