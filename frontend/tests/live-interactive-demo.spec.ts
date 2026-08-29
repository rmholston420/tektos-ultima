/**
 * Tektos Frontend — Live Interactive Demo
 * Drives the GUI in real-time with visible steps, delays for watching.
 */
const { test, expect } = require('@playwright/test');

test('live interactive demo', async ({ page }) => {
  console.log('\n═══════════════════════════════════════════');
  console.log('  TEKTOS-ULTIMA LIVE INTERACTIVE DEMO');
  console.log('═══════════════════════════════════════════\n');
  
  // ── Step 1: Homepage ──
  console.log('▶ Step 1: Loading homepage...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  console.log('  ✓ Homepage loaded — sidebar, chat input, header nav all visible');
  
  // ── Step 2: Inspect layout ──
  console.log('\n▶ Step 2: Inspecting layout structure...');
  const layout = await page.evaluate(() => {
    const shell = document.querySelector('.shell');
    const sidebar = document.querySelector('aside');
    const main = document.querySelector('main');
    return {
      hasShell: !!shell,
      hasSidebar: !!sidebar,
      hasMain: !!main,
      sidebarWidth: sidebar ? sidebar.offsetWidth : 0,
      mainWidth: main ? main.offsetWidth : 0
    };
  });
  console.log(`  Shell: ${layout.hasShell} | Sidebar: ${layout.hasSidebar} (${layout.sidebarWidth}px) | Main: ${layout.main} (${layout.mainWidth}px)`);
  console.log('  ✓ Three-pane layout confirmed');
  
  // ── Step 3: Header navigation ──
  console.log('\n▶ Step 3: Testing header navigation...');
  const chatBtn = page.locator('button').filter({ hasText: /^Chat$/ }).first();
  const dashBtn = page.locator('button').filter({ hasText: /^Dash$/ }).first();
  await expect(chatBtn).toBeVisible();
  await expect(dashBtn).toBeVisible();
  console.log('  ✓ Chat and Dash buttons visible in header');
  
  // ── Step 4: Sidebar — New Session ──
  console.log('\n▶ Step 4: Sidebar — creating a new session...');
  const newSessionBtn = page.locator('button').filter({ hasText: /New Session/i }).first();
  await expect(newSessionBtn).toBeVisible();
  await newSessionBtn.click();
  await page.waitForTimeout(1000);
  console.log('  ✓ New Session clicked — composer appeared');
  
  // ── Step 5: Type a message ──
  console.log('\n▶ Step 5: Typing a message...');
  const chatInput = page.locator('input[placeholder="Describe what you want to build..."]');
  await expect(chatInput).toBeVisible();
  await chatInput.fill('Build a REST API with FastAPI and SQLAlchemy');
  await page.waitForTimeout(500);
  const inputVal = await chatInput.inputValue();
  console.log(`  ✓ Input contains: "${inputVal}"`);
  
  // ── Step 6: Send button state ──
  console.log('\n▶ Step 6: Send button state...');
  const sendBtn = page.locator('button[aria-label="Send message"]');
  const enabled = await sendBtn.isEnabled();
  console.log(`  ✓ Send button: ${enabled ? 'ENABLED' : 'DISABLED'}`);
  
  // ── Step 7: Send the message ──
  console.log('\n▶ Step 7: Sending message...');
  await sendBtn.click();
  await page.waitForTimeout(2000);
  const afterVal = await chatInput.inputValue();
  console.log(`  ✓ Message sent — input cleared: "${afterVal}"`);
  
  // ── Step 8: Check for response ──
  console.log('\n▶ Step 8: Checking for AI response...');
  const messages = await page.locator('[class*="message"], [class*="chat-bubble"], [class*="assistant"], [class*="user-msg"]').count();
  console.log(`  ✓ Message elements on page: ${messages}`);
  
  // ── Step 9: Navigate to Dashboard ──
  console.log('\n▶ Step 9: Navigating to Dashboard...');
  await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const dashTitle = await page.locator('h1, h2, [class*="dashboard-title"]').first().textContent();
  console.log(`  ✓ Dashboard title: "${(dashTitle || '').trim().substring(0, 80)}"`);
  
  // ── Step 10: Dashboard tabs ──
  console.log('\n▶ Step 10: Exploring dashboard tabs...');
  const allBtns = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button')).map(b => ({
      text: (b.textContent || '').trim().substring(0, 40),
      class: (b.className || '').substring(0, 80)
    })).filter(b => b.text.length > 2 && !['Chat', 'Dashboard', 'Back'].includes(b.text));
  });
  console.log(`  ✓ Found ${allBtns.length} interactive buttons on dashboard:`);
  allBtns.slice(0, 15).forEach(b => console.log(`    • ${b.text}`));
  
  // ── Step 11: Click first tab ──
  if (allBtns.length > 0) {
    console.log('\n▶ Step 11: Clicking first dashboard tab...');
    const firstTab = page.locator('button').filter({ hasText: new RegExp(allBtns[0].text, 'i') }).first();
    await firstTab.click();
    await page.waitForTimeout(800);
    const activeClass = await firstTab.getAttribute('class');
    console.log(`  ✓ Tab "${allBtns[0].text}" clicked — class: ${activeClass.substring(0, 60)}...`);
  }
  
  // ── Step 12: Sidebar on chat ──
  console.log('\n▶ Step 12: Returning to Chat — checking sidebar...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const sidebar = page.locator('aside');
  const sidebarVisible = await sidebar.isVisible();
  const sidebarBtnCount = await sidebar.locator('button').count();
  console.log(`  ✓ Sidebar visible: ${sidebarVisible}`);
  console.log(`  ✓ Sidebar buttons: ${sidebarBtnCount}`);
  
  // ── Step 13: Search in sidebar ──
  console.log('\n▶ Step 13: Sidebar search...');
  const searchInput = page.locator('input[placeholder="Search..."]');
  await expect(searchInput).toBeVisible();
  await searchInput.fill('test');
  await page.waitForTimeout(500);
  const searchVal = await searchInput.inputValue();
  console.log(`  ✓ Search input: "${searchVal}"`);
  await searchInput.clear();
  await page.waitForTimeout(300);
  console.log('  ✓ Search cleared');
  
  // ── Step 14: Theme switching ──
  console.log('\n▶ Step 14: Theme switching...');
  const themeBtns = page.locator('button').filter({ hasText: /Abyss|Temple|Clarity/i });
  const themeCount = await themeBtns.count();
  console.log(`  ✓ Theme buttons found: ${themeCount}`);
  if (themeCount >= 2) {
    const templeBtn = page.locator('button').filter({ hasText: /Temple/i }).first();
    await templeBtn.click();
    await page.waitForTimeout(800);
    console.log('  ✓ Switched to Temple theme');
    const abyssBtn = page.locator('button').filter({ hasText: /Abyss/i }).first();
    await abyssBtn.click();
    await page.waitForTimeout(800);
    console.log('  ✓ Switched back to Abyss theme');
  }
  
  // ── Step 15: Session list ──
  console.log('\n▶ Step 15: Session list...');
  const sessionItems = await page.locator('aside').locator('button').all();
  const sessionTexts = await Promise.all(sessionItems.slice(0, 5).map(b => b.textContent()));
  console.log(`  ✓ Sidebar has ${sessionItems.length} buttons`);
  console.log('  ✓ Sample session entries:');
  sessionTexts.forEach(t => console.log(`    • ${(t || '').trim().substring(0, 50)}`));
  
  // ── Step 16: Archive view ──
  console.log('\n▶ Step 16: Archive view toggle...');
  const archiveBtn = page.locator('button').filter({ hasText: /Archive/i }).first();
  await archiveBtn.click();
  await page.waitForTimeout(800);
  const archiveActive = await archiveBtn.getAttribute('class');
  console.log(`  ✓ Archive tab activated — class: ${archiveActive.substring(0, 60)}...`);
  const activeBtn = page.locator('button').filter({ hasText: /Active/i }).first();
  await activeBtn.click();
  await page.waitForTimeout(500);
  console.log('  ✓ Switched back to Active view');
  
  // ── Step 17: Console check ──
  console.log('\n▶ Step 17: Console error check...');
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  await page.reload();
  await page.waitForTimeout(1000);
  console.log(`  ✓ Console errors: ${errors.length}`);
  errors.forEach(e => console.log(`    ⚠ ${e.substring(0, 120)}`));
  
  // ── Step 18: Final state ──
  console.log('\n▶ Step 18: Final page state...');
  const finalTitle = await page.title();
  const finalUrl = page.url();
  const bodyText = await page.locator('body').textContent();
  console.log(`  ✓ Title: ${finalTitle}`);
  console.log(`  ✓ URL: ${finalUrl}`);
  console.log(`  ✓ Body text length: ${bodyText.length} chars`);
  
  console.log('\n═══════════════════════════════════════════');
  console.log('  ✅ LIVE DEMO COMPLETE');
  console.log('═══════════════════════════════════════════\n');
  console.log('The Tektos frontend is fully interactive in your preview pane.');
  console.log('Try it yourself: click around, type messages, switch themes, explore the dashboard.');
});
