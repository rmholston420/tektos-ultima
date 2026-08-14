import { test, expect } from '@playwright/test';

test.describe('Tektos-Ultima Frontend E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Tektos-Ultima/);
  });

  test('sidebar renders with sessions header', async ({ page }) => {
    const sidebar = page.locator('aside');
    await expect(sidebar).toBeVisible();
    const sessionsHeader = sidebar.locator('h2', { hasText: 'Sessions' });
    await expect(sessionsHeader).toBeVisible();
  });

  test('shows "No sessions yet" initially', async ({ page }) => {
    const emptyState = page.locator('text=No sessions yet');
    await expect(emptyState).toBeVisible();
  });

  test('new session button exists', async ({ page }) => {
    const newSessionBtn = page.getByTitle('New session');
    await expect(newSessionBtn).toBeVisible();
  });

  test('header shows Tektos branding', async ({ page }) => {
    const branding = page.locator('h1', { hasText: 'Tektos-Ultima' });
    await expect(branding).toBeVisible();
  });

  test('composer area is visible but disabled without session', async ({ page }) => {
    const composer = page.locator('.composer');
    await expect(composer).toBeVisible();
    const textarea = composer.locator('textarea');
    await expect(textarea).toHaveAttribute('disabled');
  });

  test('footer shows version info', async ({ page }) => {
    const footer = page.locator('text=Tektos-Ultima v1');
    await expect(footer).toBeVisible();
  });

  test('dark theme is applied by default', async ({ page }) => {
    const html = page.locator('html');
    await expect(html).toHaveAttribute('data-theme', 'dark');
  });

  test('connection status indicator exists', async ({ page }) => {
    const status = page.locator('text=disconnected');
    await expect(status).toBeVisible();
  });
});
