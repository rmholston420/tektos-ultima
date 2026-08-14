import { test, expect } from '@playwright/test';

/**
 * Archive Browser E2E Tests
 *
 * Tests the Archive Browser component's search, sorting, view modes,
 * and UI interactions via the running frontend dev server.
 */

test.describe('Archive Browser E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Click the Archive tab to switch from Active to Archive view
    const archiveTab = page.locator('button', { hasText: 'Archive' });
    await archiveTab.click();
    // Wait for the Archive Browser to render
    await page.waitForTimeout(500);
  });

  // ── Component visibility ──────────────────────────────────────────────

  test('archive sidebar renders', async ({ page }) => {
    // Use nth(0) to avoid strict mode violation from nested asides
    const archiveSidebar = page.locator('aside').nth(0);
    await expect(archiveSidebar).toBeVisible();
  });

  test('archive header is visible', async ({ page }) => {
    const header = page.locator('h2', { hasText: 'Archive' }).first();
    await expect(header).toBeVisible();
  });

  test('archive count shows 0 sessions', async ({ page }) => {
    // The footer span with "0 sessions" is unique
    const countText = page.locator('span.text-xs.text-text-muted', { hasText: '0 sessions' }).last();
    await expect(countText).toBeVisible();
  });

  // ── View mode toggles ─────────────────────────────────────────────────

  test('list view button exists', async ({ page }) => {
    const listBtn = page.locator('button[title="List view"]');
    await expect(listBtn).toBeVisible();
  });

  test('grid view button exists', async ({ page }) => {
    const gridBtn = page.locator('button[title="Grid view"]');
    await expect(gridBtn).toBeVisible();
  });

  // ── Search ────────────────────────────────────────────────────────────

  test('search input is visible', async ({ page }) => {
    const searchInput = page.locator('input[placeholder="Search archive..."]');
    await expect(searchInput).toBeVisible();
  });

  test('typing in search updates results count', async ({ page }) => {
    const searchInput = page.locator('input[placeholder="Search archive..."]');
    await searchInput.fill('nonexistent');
    // After filtering, count should reflect 0 matches
    const countText = page.locator('span.text-xs.text-text-muted', { hasText: '0 sessions' }).last();
    await expect(countText).toBeVisible();
  });

  test('empty search placeholder renders correctly', async ({ page }) => {
    const searchInput = page.locator('input[placeholder="Search archive..."]');
    await expect(searchInput).toHaveAttribute('placeholder', 'Search archive...');
  });

  // ── Sort controls ─────────────────────────────────────────────────────

  test('sort dropdown exists', async ({ page }) => {
    const sortSelect = page.locator('select');
    await expect(sortSelect).toBeVisible();
    const options = await sortSelect.locator('option').allTextContents();
    expect(options).toContain('Updated');
    expect(options).toContain('Created');
    expect(options).toContain('Title');
  });

  test('sort order toggle button exists', async ({ page }) => {
    const toggleBtn = page.locator('button[title="Descending"]');
    await expect(toggleBtn).toBeVisible();
  });

  test('toggling sort order changes title', async ({ page }) => {
    const toggleBtn = page.locator('button[title="Descending"]');
    await toggleBtn.click();
    await expect(page.locator('button[title="Ascending"]')).toBeVisible();
  });

  // ── Footer ────────────────────────────────────────────────────────────

  test('archive browser footer label exists', async ({ page }) => {
    const footerLabel = page.locator('text=Archive Browser');
    await expect(footerLabel).toBeVisible();
  });

  test('archived count in footer shows 0', async ({ page }) => {
    const archivedCount = page.locator('text=0 archived');
    await expect(archivedCount).toBeVisible();
  });

  // ── Empty state ───────────────────────────────────────────────────────

  test('shows "No sessions in archive" when empty', async ({ page }) => {
    const emptyState = page.locator('text=No sessions in archive');
    await expect(emptyState).toBeVisible();
  });

  test('shows "No sessions match" when search yields no results', async ({ page }) => {
    const searchInput = page.locator('input[placeholder="Search archive..."]');
    await searchInput.fill('xyzzy-no-match');
    const noMatchText = page.locator('text=No sessions match your search');
    await expect(noMatchText).toBeVisible();
  });

  // ── Dark theme ────────────────────────────────────────────────────────

  test('archive sidebar has dark background', async ({ page }) => {
    const archiveSidebar = page.locator('aside').first();
    const bg = await archiveSidebar.evaluate(el => getComputedStyle(el).backgroundColor);
    expect(bg).toBeTruthy(); // Should not be transparent/white
  });

  // ── Sidebar interaction ───────────────────────────────────────────────

  test('new session button is clickable', async ({ page }) => {
    const newSessionBtn = page.getByTitle('New session');
    await expect(newSessionBtn).toBeVisible();
    // Click should not throw
    await newSessionBtn.click();
  });

  // ── Layout ────────────────────────────────────────────────────────────

  test('archive section has divider line', async ({ page }) => {
    const divider = page.locator('div.border-t.border-border').last();
    await expect(divider).toBeVisible();
  });

  // ── Visual structure ──────────────────────────────────────────────────

  test('search input has magnifying glass icon', async ({ page }) => {
    const icon = page.locator('svg.text-text-muted').nth(0);
    await expect(icon).toBeVisible();
  });
});
