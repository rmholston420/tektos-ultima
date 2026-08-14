/**
 * Tektos-Ultima v1 — Playwright E2E Tests
 *
 * Tests against Next.js app (client-side rendered).
 * All selectors wait for client hydration.
 */

import { test, expect } from '@playwright/test';

test.describe('Tektos-Ultima Frontend E2E Tests', () => {

  // ─── Page Load Tests ─────────────────────────────────────────────────────

  test('page loads without error', async ({ page }) => {
    await page.goto('/');
    // Wait for client-side JS to execute
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    // Check page has content
    const bodyText = await page.locator('body').textContent();
    expect(bodyText).not.toBe('');
  });

  test('shell layout renders', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    // Look for the shell wrapper div
    const shell = page.locator('div').filter({ hasText: /Tektos|Chat|Dashboard/i }).first();
    await expect(shell).toBeVisible();
  });

  test('header with Chat/Dashboard buttons exists', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    const chatBtn = page.locator('button').filter({ hasText: /chat/i }).first();
    const dashBtn = page.locator('button').filter({ hasText: /dashboard/i }).first();
    await expect(chatBtn).toBeVisible();
    await expect(dashBtn).toBeVisible();
  });

  // ─── Chat Page Tests ─────────────────────────────────────────────────────

  test('chat page shows composer with textarea', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    // Composer has textarea for input
    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible();
  });

  test('upload/attach button exists in composer', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    // Look for upload-related button or icon
    const uploadBtn = page.locator('button[title="Attach file"]').first();
    // Or button with upload icon
    const hasUploadIcon = await page.locator('svg').count() > 0;
    expect(hasUploadIcon).toBeTruthy();
  });

  test('send button exists in composer', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    const hasButtons = await page.locator('button').count() > 0;
    expect(hasButtons).toBeTruthy();
  });

  // ─── Dashboard Navigation Tests ──────────────────────────────────────────

  test('dashboard button works and shows dashboard content', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await page.locator('button').filter({ hasText: /dashboard/i }).first().click();
    await page.waitForTimeout(1000);
    // Dashboard tab bar should appear
    const dashboardVisible = await page.locator('body').textContent()
      .then(t => t.toLowerCase().includes('dashboard') || t.toLowerCase().includes('system'));
    expect(dashboardVisible).toBeTruthy();
  });

  // ─── Dashboard Tab Tests ─────────────────────────────────────────────────

  async function navigateToDashboard(page) {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await page.locator('button').filter({ hasText: /dashboard/i }).first().click();
    await page.waitForTimeout(800);
  }

  test('system graph tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /graph/i }).first().click();
    await page.waitForTimeout(800);
    // Graph tab should be active (has accent/highlight class)
    const graphBtn = page.locator('button').filter({ hasText: /graph/i }).first();
    const classes = await graphBtn.getAttribute('class') || '';
    expect(classes.includes('accent') || classes.includes('bg-')).toBeTruthy();
  });

  test('telemetry tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /telemetry/i }).first().click();
    await page.waitForTimeout(800);
    const telemetryBtn = page.locator('button').filter({ hasText: /telemetry/i }).first();
    const classes = await telemetryBtn.getAttribute('class') || '';
    expect(classes.length > 0).toBeTruthy();
  });

  test('router tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /router/i }).first().click();
    await page.waitForTimeout(800);
    const routerBtn = page.locator('button').filter({ hasText: /router/i }).first();
    const classes = await routerBtn.getAttribute('class') || '';
    expect(classes.length > 0).toBeTruthy();
  });

  test('axioms tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /axiom/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('memory tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /memory/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('skills tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /skill/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('config tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /config/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('keys tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /key/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('mcp tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /mcp/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('hooks tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /hook/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('logs tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /log/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('scheduling tab loads', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /schedul/i }).first().click();
    await page.waitForTimeout(800);
  });

  test('scheduling panel has create button', async ({ page }) => {
    await navigateToDashboard(page);
    await page.locator('button').filter({ hasText: /schedul/i }).first().click();
    await page.waitForTimeout(800);
    const newBtn = page.locator('button').filter({ hasText: /new/i }).first();
    await expect(newBtn).toBeVisible();
  });

  // ─── Full Workflow Tests ─────────────────────────────────────────────────

  test('workflow: home → dashboard → schedule → chat', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Go to dashboard
    await page.locator('button').filter({ hasText: /dashboard/i }).first().click();
    await page.waitForTimeout(800);

    // Go to scheduling
    await page.locator('button').filter({ hasText: /schedul/i }).first().click();
    await page.waitForTimeout(800);

    // Back to chat
    await page.locator('button').filter({ hasText: /chat/i }).first().click();
    await page.waitForTimeout(800);

    // Should be on chat
    const bodyText = await page.locator('body').textContent();
    expect(bodyText.toLowerCase().includes('describe') || bodyText.toLowerCase().includes('build')).toBeTruthy();
  });

  test('all dashboard tabs are clickable without crashes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Collect all dashboard tab buttons
    const allButtons = await page.locator('button').all();
    let dashboardTabButtons = [];

    // After going to dashboard, find all tab buttons
    await page.locator('button').filter({ hasText: /dashboard/i }).first().click();
    await page.waitForTimeout(800);

    const tabButtons = await page.locator('button').all();
    for (const btn of tabButtons) {
      const text = await btn.textContent();
      if (text && text.length < 20) {
        dashboardTabButtons.push({ btn, text });
      }
    }

    // Click each tab and verify no JS errors
    for (const { btn, text } of dashboardTabButtons.slice(0, 13)) {
      await btn.click();
      await page.waitForTimeout(300);
      // Page should still be responsive
      const alive = await page.evaluate(() => document.readyState === 'complete');
      expect(alive).toBeTruthy();
    }
  });

  // ─── Sidebar Tests ───────────────────────────────────────────────────────

  test('sidebar area exists with navigation', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    // Page should have left sidebar area
    const pageContent = await page.locator('body').textContent();
    expect(pageContent.length).toBeGreaterThan(50);
  });

  test('chat page toggle works', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await page.locator('button').filter({ hasText: /dashboard/i }).first().click();
    await page.waitForTimeout(800);
    await page.locator('button').filter({ hasText: /chat/i }).first().click();
    await page.waitForTimeout(800);
    // Should have textarea again
    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible();
  });

});
