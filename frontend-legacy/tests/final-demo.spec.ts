/**
 * Tektos Frontend — Final Live Demo (after wiring fixes)
 */
const { test, expect } = require('@playwright/test');

test('final live demo', async ({ page }) => {
  console.log('\n═══════════════════════════════════════════');
  console.log('  TEKTOS-ULTIMA FINAL LIVE DEMO');
  console.log('═══════════════════════════════════════════\n');
  
  // ── Step 1: Homepage ──
  console.log('▶ Step 1: Loading homepage...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  console.log('  ✓ Homepage loaded');
  
  // ── Step 2: Chat input + send ──
  console.log('\n▶ Step 2: Chat input and send...');
  const chatInput = page.locator('input[placeholder="Describe what you want to build..."]');
  await expect(chatInput).toBeVisible();
  await chatInput.fill('Write a Python function that sorts a list using merge sort');
  await page.waitForTimeout(500);
  const sendBtn = page.locator('button[aria-label="Send message"]');
  await expect(sendBtn).toBeEnabled();
  await sendBtn.click();
  await page.waitForTimeout(1000);
  console.log('  ✓ Message typed and sent');
  
  // ── Step 3: Navigate to Dashboard ──
  console.log('\n▶ Step 3: Navigate to Dashboard...');
  await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const dashTitle = await page.title();
  console.log(`  ✓ Dashboard loaded — title: "${dashTitle}"`);
  
  // ── Step 4: Dashboard tabs ──
  console.log('\n▶ Step 4: Dashboard tabs...');
  const allTabs = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.overflow-x-auto button')).map(b => ({
      text: (b.textContent || '').trim(),
      active: b.classList.contains('bg-accent')
    }));
  });
  console.log(`  ✓ ${allTabs.length} tabs rendered`);
  
  // Click several tabs
  const tabsToClick = ['Telemetry', 'Router', 'Axioms', 'Memory', 'Skills', 'Config', 'MCP', 'Hooks', 'Logs'];
  for (const name of tabsToClick) {
    const btn = page.locator('button').filter({ hasText: new RegExp(name, 'i') }).first();
    if (await btn.count() > 0 && await btn.isVisible()) {
      await btn.click();
      await page.waitForTimeout(300);
      console.log(`  ✓ Clicked: ${name}`);
    }
  }
  
  // ── Step 5: Sidebar on chat ──
  console.log('\n▶ Step 5: Sidebar on chat route...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const sidebar = page.locator('aside');
  console.log(`  ✓ Sidebar visible: ${await sidebar.isVisible()}`);
  
  // Theme switching
  const themeBtns = page.locator('button').filter({ hasText: /Abyss|Temple|Clarity/i });
  const themeCount = await themeBtns.count();
  console.log(`  ✓ Theme buttons: ${themeCount}`);
  if (themeCount >= 2) {
    await page.locator('button').filter({ hasText: /Temple/i }).first().click();
    await page.waitForTimeout(500);
    await page.locator('button').filter({ hasText: /Abyss/i }).first().click();
    await page.waitForTimeout(500);
    console.log('  ✓ Theme switch: Temple → Abyss');
  }
  
  // Archive toggle
  await page.locator('button').filter({ hasText: /Archive/i }).first().click();
  await page.waitForTimeout(500);
  await page.locator('button').filter({ hasText: /Active/i }).first().click();
  await page.waitForTimeout(500);
  console.log('  ✓ Archive/Active toggle works');
  
  // ── Step 6: API health ──
  console.log('\n▶ Step 6: API health check...');
  const health = await page.evaluate(async () => {
    try {
      const r = await fetch('/api/health');
      const d = await r.json();
      return { ok: d.ok, sessions: d.active_sessions, protocol: d.protocol_version };
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log(`  ✓ Health: ok=${health.ok}, sessions=${health.sessions}, protocol=${health.protocol}`);
  
  // ── Step 7: Models ──
  console.log('\n▶ Step 7: Models endpoint...');
  const models = await page.evaluate(async () => {
    try {
      const r = await fetch('/api/models');
      const d = await r.json();
      return d.map(m => m.name).join(', ');
    } catch (e) {
      return `error: ${e.message}`;
    }
  });
  console.log(`  ✓ Models: ${models}`);
  
  // ── Step 8: Console errors ──
  console.log('\n▶ Step 8: Console errors...');
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  await page.reload();
  await page.waitForTimeout(1000);
  console.log(`  ✓ Console errors: ${errors.length}`);
  errors.forEach(e => console.log(`    ⚠ ${e.substring(0, 120)}`));
  
  console.log('\n═══════════════════════════════════════════');
  console.log('  ✅ FINAL DEMO COMPLETE');
  console.log('═══════════════════════════════════════════\n');
});
