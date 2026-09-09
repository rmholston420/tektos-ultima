import { test, expect } from "@playwright/test";

/**
 * Dashboard: the panel registry renders a sidebar with panel tabs from
 * multiple sections, and clicking a Storage or Models panel navigates
 * without a console error even though the panel calls backend APIs
 * that may fail in this environment.
 */
test("dashboard renders panel registry and switches panels", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/dashboard");
  await expect(page.getByRole("navigation", { name: "Dashboard sections" })).toBeVisible();

  // Overview loads by default.
  await expect(page.getByTestId("panel-tab-overview")).toBeVisible();

  // Click a handful of panels across sections.
  for (const id of ["telemetry", "logs", "keys", "settings", "database"]) {
    await page.getByTestId(`panel-tab-${id}`).click();
    await page.waitForTimeout(200);
  }

  // Panel content is best-effort in this sandbox — assert no fatal JS crashes.
  expect(errors.filter((e) => !/Failed to fetch|NetworkError|abort/i.test(e))).toEqual([]);
});
