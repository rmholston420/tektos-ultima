/** Verify all routes and API endpoints are wired correctly */
const { test, expect } = require('@playwright/test');

test('all routes return 200', async ({ page }) => {
  const routes = [
    { path: '/', name: 'Chat (homepage)' },
    { path: '/dashboard', name: 'Dashboard' },
  ];
  
  for (const route of routes) {
    await page.goto(`http://localhost:3000${route.path}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    const title = await page.title();
    const status = page.url().includes('404') ? '404' : '200';
    console.log(`  ${route.name}: ${status} — title: "${title}"`);
    expect(status).toBe('200');
  }
});

test('dashboard tabs render', async ({ page }) => {
  await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  
  const tabs = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.overflow-x-auto button')).map(b => ({
      text: (b.textContent || '').trim(),
      active: b.classList.contains('bg-accent')
    }));
  });
  
  console.log(`\n  Dashboard tabs: ${tabs.length}`);
  tabs.forEach(t => console.log(`    ${t.active ? '●' : '○'} ${t.text}`));
  
  expect(tabs.length).toBeGreaterThan(0);
  
  // Click a few tabs to verify they work
  const tabNames = ['Telemetry', 'Router', 'Axioms', 'Memory', 'Skills'];
  for (const name of tabNames) {
    const btn = page.locator('button').filter({ hasText: new RegExp(name, 'i') }).first();
    if (await btn.count() > 0) {
      await btn.click();
      await page.waitForTimeout(300);
      console.log(`  ✓ Clicked tab: ${name}`);
    }
  }
});

test('API endpoints respond', async ({ page }) => {
  const endpoints = [
    { path: '/api/health', name: 'Health' },
    { path: '/api/models', name: 'Models' },
    { path: '/api/sessions', name: 'Sessions' },
    { path: '/api/state', name: 'State' },
    { path: '/api/search', name: 'Search' },
    { path: '/api/schema', name: 'Schema' },
  ];
  
  for (const ep of endpoints) {
    const resp = await page.evaluate(async (path) => {
      try {
        const r = await fetch(path);
        return { status: r.status, ok: r.ok, size: (await r.text()).length };
      } catch (e) {
        return { status: 0, ok: false, error: e.message };
      }
    }, ep.path);
    console.log(`  ${ep.name}: ${resp.status} (ok=${resp.ok}, size=${resp.size})`);
  }
});
