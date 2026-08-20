const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  
  const logs = [];
  p.on('console', msg => {
    if (!msg.text().includes('React DevTools') && !msg.text().includes('favicon')) {
      logs.push(msg.text());
    }
  });
  
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(3000);
  
  // Inject WS interceptor
  await p.evaluate(() => {
    const origWS = window.WebSocket;
    window.WebSocket = function(url) {
      const ws = new origWS(url);
      ws.addEventListener('open', () => console.log('WS-OPEN'));
      ws.addEventListener('message', e => { try { console.log('WS-MSG:', JSON.parse(e.data).event_type || e.data.substring(0, 50)); } catch {} });
      ws.addEventListener('close', () => console.log('WS-CLOSE'));
      ws.addEventListener('error', () => console.log('WS-ERROR'));
      const origSend = ws.send.bind(ws);
      ws.send = function(data) { try { console.log('WS-SEND:', JSON.parse(data).type); } catch { console.log('WS-SEND: (raw)'); } return origSend(data); };
      return ws;
    };
  });
  
  // Create session
  await p.click('button:has-text("New Session")');
  await p.waitForTimeout(3000);
  
  // Wait for WS
  await p.waitForTimeout(2000);
  
  // Type and send
  const textarea = await p.$('textarea');
  if (textarea) {
    await textarea.click();
    await textarea.pressSequentially('Write a Python function that reverses a string.', { delay: 10 });
    await p.waitForTimeout(500);
    
    await p.click('button[title="Send message"]');
    await p.waitForTimeout(12000);
  }
  
  // Results
  const messages = await p.$$('.message-card');
  const assistants = await p.$$('.message-card-assistant');
  
  console.log('=== RESULTS ===');
  console.log('Messages:', messages.length);
  console.log('Assistant cards:', assistants.length);
  
  logs.forEach(l => console.log(' ', l));
  
  if (assistants.length > 0) {
    const text = await assistants[assistants.length-1].evaluate(el => el.innerText);
    console.log('Assistant:', text.substring(0, 200));
  }
  
  await b.close();
})();