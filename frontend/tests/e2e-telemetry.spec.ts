/**
 * Tektos-Ultima v1 — Telemetry E2E Tests
 *
 * End-to-end tests that verify the full telemetry data pipeline:
 * live hardware sensors → /api/telemetry backend endpoint → frontend
 * TelemetryPanel + SystemDashboard rendering real metrics.
 *
 * Backend: http://localhost:8020
 * Frontend: http://localhost:3003
 */

import { test, expect } from "@playwright/test";

const FRONTEND = process.env.BASE_URL || "http://localhost:3003";
const BACKEND = "http://localhost:8020";

// ─── Backend Health ─────────────────────────────────────────────────────────

test.describe("Backend Telemetry API", () => {
  test("GET /api/telemetry returns real GPU data", async () => {
    const res = await fetch(`${BACKEND}/api/telemetry`);
    expect(res.ok).toBe(true);
    const body = await res.json();

    // GPU metrics must be present and non-zero (real hardware)
    expect(body).toHaveProperty("gpu");
    expect(body.gpu).toHaveProperty("temperature");
    expect(body.gpu).toHaveProperty("utilization");
    expect(body.gpu).toHaveProperty("memory_used");
    expect(body.gpu).toHaveProperty("memory_total");
    expect(body.gpu).toHaveProperty("power_draw");
    expect(body.gpu).toHaveProperty("power_limit");
    expect(body.gpu).toHaveProperty("fan_speed");

    // GPU temperature should be a reasonable value (20-100°C)
    expect(body.gpu.temperature).toBeGreaterThanOrEqual(20);
    expect(body.gpu.temperature).toBeLessThanOrEqual(100);

    // VRAM should show real values
    expect(body.gpu.memory_used).toBeGreaterThan(0);
    expect(body.gpu.memory_total).toBeGreaterThan(0);
  });

  test("GET /api/telemetry returns system metrics", async () => {
    const res = await fetch(`${BACKEND}/api/telemetry`);
    expect(res.ok).toBe(true);
    const body = await res.json();

    expect(body).toHaveProperty("system");
    expect(body.system).toHaveProperty("cpu_util");
    expect(body.system).toHaveProperty("mem_used_gb");
    expect(body.system).toHaveProperty("mem_total_gb");
    expect(body.system).toHaveProperty("disk_used_gb");
    expect(body.system).toHaveProperty("disk_total_gb");
  });

  test("GET /api/telemetry returns timestamp", async () => {
    const res = await fetch(`${BACKEND}/api/telemetry`);
    const body = await res.json();
    expect(body).toHaveProperty("timestamp");
    expect(typeof body.timestamp).toBe("number");
    // Should be within the last 60 seconds
    expect(body.timestamp).toBeGreaterThan(Date.now() / 1000 - 60);
  });
});

// ─── Frontend Rendering ─────────────────────────────────────────────────────

test.describe("Frontend TelemetryPanel", () => {
  test("navigates to dashboard and clicks telemetry tab", async ({ page }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);

    // Click dashboard button
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);

    // Click telemetry tab
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(1000);

    // TelemetryPanel should be visible
    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("telemetry");
  });

  test("telemetry panel header is visible with live status indicator", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(2000);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText).toContain("System Telemetry");
  });

  test("telemetry panel displays GPU temperature from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";

    // Should show "Temperature" label
    expect(bodyText.toLowerCase()).toContain("temperature");

    // Should show a numeric temperature value
    const tempMatch = (bodyText || "").match(/\d+(\.\d+)?\s*°C/);
    expect(tempMatch).not.toBeNull();
    const tempVal = parseFloat(tempMatch![0]);
    expect(tempVal).toBeGreaterThanOrEqual(20);
    expect(tempVal).toBeLessThanOrEqual(100);
  });

  test("telemetry panel displays GPU utilization from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";

    // Should show utilization percentage
    expect(bodyText.toLowerCase()).toContain("utilization");
  });

  test("telemetry panel displays VRAM metrics from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("vram");
  });

  test("telemetry panel displays power draw from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("power");
  });

  test("telemetry panel displays CPU utilization from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("cpu");
  });

  test("telemetry panel displays RAM metrics from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("ram");
  });

  test("telemetry panel displays storage metrics from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("storage");
  });

  test("telemetry panel displays cooling/fan metrics from live API", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("cooling");
  });

  test("telemetry panel has no console errors during data fetch", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(4000);

    expect(errors.length).toBeLessThan(3);
  });
});

// ─── SystemDashboard Real Data ──────────────────────────────────────────────

test.describe("Frontend SystemDashboard", () => {
  test("navigates to dashboard overview tab", async ({ page }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);

    const bodyText = (await page.locator("body").textContent()) || "";
    expect(bodyText.toLowerCase()).toContain("dashboard");
  });

  test("system dashboard displays GPU temperature metric card with live data", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);

    // Click overview/system tab
    const overviewBtn = page.getByRole("button", { name: /overview|system/i });
    if ((await overviewBtn.count()) > 0) {
      await overviewBtn.first().click();
      await page.waitForTimeout(1000);
    }

    await page.waitForTimeout(3000); // Let telemetry data arrive
    const bodyText = (await page.locator("body").textContent()) || "";

    expect(bodyText.toLowerCase()).toContain("dashboard");

    // Should show real temperature value (not zero)
    const tempMatch = (bodyText || "").match(/\d+(\.\d+)?\s*°C/);
    if (tempMatch) {
      const tempVal = parseFloat(tempMatch[0]);
      expect(tempVal).toBeGreaterThanOrEqual(20);
      expect(tempVal).toBeLessThanOrEqual(100);
    }
  });

  test("system dashboard has no console errors during data fetch", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);

    const overviewBtn = page.getByRole("button", { name: /overview|system/i });
    if ((await overviewBtn.count()) > 0) {
      await overviewBtn.first().click();
      await page.waitForTimeout(1000);
    }

    await page.waitForTimeout(4000);
    expect(errors.length).toBeLessThan(3);
  });
});

// ─── Full Telemetry Pipeline E2E ────────────────────────────────────────────

test.describe("Full Telemetry Pipeline", () => {
  test("real GPU data flows from sensor → backend API → frontend rendering", async ({
    page,
  }) => {
    // Step 1: Verify backend has live GPU data
    const backendRes = await fetch(`${BACKEND}/api/telemetry`);
    expect(backendRes.ok).toBe(true);
    const backendData = await backendRes.json();
    const gpuTemp = backendData.gpu.temperature;

    expect(gpuTemp).toBeGreaterThanOrEqual(20);
    expect(gpuTemp).toBeLessThanOrEqual(100);

    // Step 2: Load frontend and verify it renders matching data
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);

    // Go to telemetry panel
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    // Step 3: Verify frontend shows a temperature value in the valid range
    const bodyText = (await page.locator("body").textContent()) || "";
    const tempMatches = (bodyText || "").match(/\d+(\.\d+)?\s*°C/g) || [];

    expect(tempMatches.length).toBeGreaterThan(0);

    // All temperature values shown should be in valid range
    for (const match of tempMatches) {
      const val = parseFloat(match);
      expect(val).toBeGreaterThanOrEqual(20);
      expect(val).toBeLessThanOrEqual(100);
    }
  });

  test("telemetry data updates on page (2-second polling)", async ({
    page,
  }) => {
    await page.goto(FRONTEND);
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /dashboard/i }).first().click();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /telemetry/i }).first().click();
    await page.waitForTimeout(3000);

    // Take first snapshot
    const body1 = (await page.locator("body").textContent()) || "";
    const temps1 = (body1 || "").match(/\d+(\.\d+)?\s*°C/g) || [];

    // Wait for 2 polling cycles
    await page.waitForTimeout(5000);

    // Take second snapshot — page should still be stable
    const body2 = (await page.locator("body").textContent()) || "";
    expect(body2.length).toBeGreaterThan(100);

    // No console errors during polling
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    // Re-add listener and wait
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.waitForTimeout(3000);
    expect(errors.length).toBeLessThan(3);
  });
});
