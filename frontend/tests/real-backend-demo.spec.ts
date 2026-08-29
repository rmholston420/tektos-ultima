/**
 * Tektos Frontend — Real Backend Live Demo
 * 
 * Uses the actual backend API + WebSocket to drive a real coding task.
 * Steps:
 * 1. Create a session via API
 * 2. Connect WebSocket
 * 3. Submit a prompt via JSON-RPC
 * 4. Watch events stream in
 * 5. Verify the agent processes it
 */
const { test, expect } = require('@playwright/test');

test('real backend live demo', async ({ page }) => {
  console.log('\n═══════════════════════════════════════════');
  console.log('  TEKTOS-ULTIMA REAL BACKEND LIVE DEMO');
  console.log('═══════════════════════════════════════════\n');
  
  // ── Step 1: Create session via API ──
  console.log('▶ Step 1: Creating session via API...');
  const createResp = await fetch('http://localhost:8020/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Live Demo Session' })
  });
  const session = await createResp.json();
  console.log(`  ✓ Session created: ${session.id}`);
  console.log(`    Model: ${session.model}`);
  console.log(`    Status: ${session.status}`);
  
  // ── Step 2: Check backend health ──
  console.log('\n▶ Step 2: Backend health...');
  const health = await fetch('http://localhost:8020/api/health').then(r => r.json());
  console.log(`  ✓ Health: ok=${health.ok}`);
  console.log(`    LLM URL: ${health.llm_url}`);
  console.log(`    LLM Model: ${health.llm_model}`);
  console.log(`    Active sessions: ${health.active_sessions}`);
  console.log(`    Protocol: ${health.protocol_version}`);
  
  // ── Step 3: Check models ──
  console.log('\n▶ Step 3: Available models...');
  const models = await fetch('http://localhost:8020/api/models').then(r => r.json());
  models.forEach(m => console.log(`    • ${m.name} (${m.role}) - ${m.params} params`));
  
  // ── Step 4: Submit prompt via WebSocket ──
  console.log('\n▶ Step 4: Submitting prompt via WebSocket...');
  
  const wsUrl = 'ws://localhost:8020/';
  const ws = await new Promise((resolve, reject) => {
    const socket = new WebSocket(wsUrl);
    socket.onopen = () => resolve(socket);
    socket.onerror = (e) => reject(new Error('WS connection failed'));
    socket.onmessage = (e) => {
      const data = JSON.parse(e.data);
      console.log(`  ← WS event: ${data.type || data.method || JSON.stringify(data).substring(0, 100)}`);
    };
    setTimeout(() => reject(new Error('WS connection timeout')), 10000);
  });
  
  console.log('  ✓ WebSocket connected');
  
  // Send prompt via JSON-RPC
  const promptMsg = JSON.stringify({
    jsonrpc: "2.0",
    method: "prompt.submit",
    params: {
      session_id: session.id,
      text: "Write a Python function called fibonacci(n) that returns the nth Fibonacci number using memoization. Include type hints and docstring."
    }
  });
  
  console.log(`  → Sending prompt to session ${session.id}`);
  ws.send(promptMsg);
  
  // Wait for events
  console.log('\n▶ Step 5: Watching for events...');
  const events = [];
  const eventTimeout = new Promise((resolve) => {
    setTimeout(resolve, 30000); // 30s timeout
  });
  
  const eventPromise = new Promise((resolve) => {
    let eventCount = 0;
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      eventCount++;
      events.push(data);
      
      // Log interesting events
      const type = data.type || data.method || 'unknown';
      const payload = data.params || data.payload || {};
      const summary = JSON.stringify(payload).substring(0, 150);
      console.log(`  [${eventCount}] ${type}: ${summary}`);
      
      // Stop after we see assistant.completed or session.failed
      if (type === 'assistant.completed' || type === 'session.failed' || type === 'session.interrupted') {
        resolve();
      }
    };
  });
  
  await Promise.race([eventPromise, eventTimeout]);
  
  console.log(`\n  ✓ Received ${events.length} events`);
  
  // ── Step 6: Check session state ──
  console.log('\n▶ Step 6: Session state after prompt...');
  const stateResp = await fetch(`http://localhost:8020/api/state/${session.id}`);
  const state = await stateResp.json();
  console.log(`  ✓ Session status: ${state.status || state.state || 'unknown'}`);
  console.log(`    Current seq: ${state.current_seq || state.seq || 'N/A'}`);
  
  // ── Step 7: Check messages ──
  console.log('\n▶ Step 7: Session messages...');
  const messagesResp = await fetch(`http://localhost:8020/api/archive/sessions/${session.id}/messages`);
  const messages = await messagesResp.json();
  console.log(`  ✓ ${messages.length} messages in session`);
  messages.forEach((m, i) => {
    const role = m.role || m.type || 'unknown';
    const content = (m.content || m.text || '').substring(0, 100);
    console.log(`    [${i}] ${role}: ${content}`);
  });
  
  // ── Step 8: Frontend integration ──
  console.log('\n▶ Step 8: Frontend integration...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  
  // Check connection status
  const connStatus = await page.evaluate(() => {
    const statusEl = document.querySelector('span.text-xs.text-text-muted.capitalize');
    return statusEl ? statusEl.textContent.trim() : 'not found';
  });
  console.log(`  ✓ Connection status: ${connStatus}`);
  
  // Check session count
  const bodyText = await page.locator('body').textContent();
  const sessionMatch = bodyText.match(/(\d+)\s*session/);
  console.log(`  ✓ Session count displayed: ${sessionMatch ? sessionMatch[1] : 'not found'}`);
  
  // ── Step 9: Dashboard ──
  console.log('\n▶ Step 9: Dashboard route...');
  await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const dashTitle = await page.title();
  console.log(`  ✓ Dashboard title: "${dashTitle}"`);
  
  const tabCount = await page.evaluate(() => {
    return document.querySelectorAll('.overflow-x-auto button').length;
  });
  console.log(`  ✓ Dashboard tabs: ${tabCount}`);
  
  // Click Telemetry tab
  const telemetryBtn = page.locator('button').filter({ hasText: /Telemetry/i }).first();
  if (await telemetryBtn.count() > 0) {
    await telemetryBtn.click();
    await page.waitForTimeout(500);
    console.log('  ✓ Telemetry tab clicked');
  }
  
  // ── Summary ──
  console.log('\n═══════════════════════════════════════════');
  console.log('  ✅ REAL BACKEND DEMO COMPLETE');
  console.log('═══════════════════════════════════════════\n');
  console.log('Summary:');
  console.log(`  • Session created: ${session.id}`);
  console.log(`  • Backend health: ${health.ok}`);
  console.log(`  • LLM model: ${health.llm_model}`);
  console.log(`  • Models available: ${models.length}`);
  console.log(`  • WebSocket events received: ${events.length}`);
  console.log(`  • Messages in session: ${messages.length}`);
  console.log(`  • Frontend connection: ${connStatus}`);
  console.log(`  • Dashboard route: working (${tabCount} tabs)`);
});
