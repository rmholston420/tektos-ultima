import { test, expect } from "@playwright/test";

/**
 * Route-level smoke: every top-level destination renders its landmark
 * heading and the app shell renders LeftRail + RightRail on each.
 */
const ROUTES: Array<{ path: string; landmark: RegExp }> = [
  { path: "/", landmark: /composer/i },
  { path: "/artifacts", landmark: /Artifacts/i },
  { path: "/runs", landmark: /Runs/i },
  { path: "/dashboard", landmark: /Dashboard/i },
  { path: "/settings", landmark: /Settings/i },
];

for (const { path, landmark } of ROUTES) {
  test(`route ${path} renders shell + content`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("navigation", { name: "Navigation" })).toBeVisible();
    await expect(page.getByRole("complementary", { name: "Contextual pane" })).toBeVisible();
    // Landmark check: either heading text or an aria label / placeholder we own
    if (path === "/") {
      await expect(page.locator("textarea, [role='textbox']").first()).toBeVisible();
    } else {
      await expect(page.getByRole("heading", { name: landmark })).toBeVisible();
    }
  });
}
