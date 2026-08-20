const { chromium } = require('playwright');

(async () => {
  console.log('🔍 Tektos Debug - WS Flow Analysis\n');
  
  const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  
  // Intercept console logs
  const logs = [];
  p.on('console', msg => {
    if (!msg.text().includes('React DevTools')) {
      logs.push(`[LOG] ${msg.text()}`);
    }
  });
  
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(3000);
  
  // Inject WebSocket interceptor to log all WS activity
  await p.evaluate(() => {
    const origWS = window.WebSocket;
    window.WebSocket = function(url, protocols) {
      const ws = new origWS(url, protocols);
      
      ws.addEventListener('open', () => {
        console.log('WS OPENED:', url);
        console.log('WS readyState:', ws.readyState);
      });
      
      ws.addEventListener('message', (e) => {
        try {
          const d = JSON.parse(e.data);
          console.log('WS RECV:', (d.event_type || d.type || 'unknown'), JSON.stringify(d.payload || {}).substring(0, 80));
        } catch {
          console.log('WS RECV (raw):', e.data.substring(0, 80));
        }
      });
      
      ws.addEventListener('close', (e) => {
        console.log('WS CLOSED:', e.code, e.reason);
      });
      
      ws.addEventListener('error', () => {
        console.log('WS ERROR');
      });
      
      const origSend = ws.send.bind(ws);
      ws.send = function(data) {
        try {
          const d = JSON.parse(data);
          console.log('WS SEND:', d.type || 'unknown', JSON.stringify(d).substring(0, 100));
        } catch {
          console.log('WS SEND (raw):', data.substring(0, 80));
        }
        return origSend(data);
      };
      
      return ws;
    };
  });
  
  console.log('1. Page loaded');
  await p.screenshot({ path: '/tmp/tektos-1.png' });
  
  console.log('2. Creating session...');
  await p.click('button:has-text("New Session")');
  await p.waitForTimeout(3000);
  await p.screenshot({ path: '/tmp/tektos-2.png' });
  
  console.log('3. Waiting for WS...');
  await p.waitForTimeout(2000);
  
  console.log('4. Typing task...');
  const textarea = await p.$('textarea');
  if (textarea) {
    await textarea.click();
    await textarea.type('Write a Python function that reverses a string.', { delay: 15 });
    await p.waitForTimeout(1000);
    await p.screenshot({ path: '/tmp/tektos-3.png' });
  }
  
  console.log('5. Clicking Send...');
  const sendBtn = await p.$('button[title="Send message"]');
  if (sendBtn) {
    const disabled = await sendBtn.evaluate(el => el.disabled);
    console.log(`   Send disabled: ${disabled}`);
    
    if (!disabled) {
      await sendBtn.click();
      console.log('   Message sent!');
      await p.screenshot({ path: '/tmp/tektos-4.png' });
      
      console.log('6. Waiting for LLM response (15s)...');
      await p.waitForTimeout(15000);
      await p.screenshot({ path: '/tmp/tektos-5.png' });
      
      const messages = await p.$$('.message-card');
      console.log(`   Messages: ${messages.length}`);
      
      const assistant = await p.$$('.message-card-assistant');
      console.log(`   Assistant cards: ${assistant.length}`);
      
      if (assistant.length > 0) {
        const text = await assistant[assistant.length-1].evaluate(el => el.innerText);
        console.log(`   Content preview: ${text.substring(0, 200)}...`);
      }
    } else {
      console.log('   ⚠️ Still disabled');
      // Check session state
      const status = await p.evaluate(() => {
        const els = document.querySelectorAll('[class*="status"], [class*="state"]');
        return Array.from(els).map(e => ({ tag: e.tagName, text: e.innerText, class: e.className })).slice(0, 5);
      });
      console.log('   Status elements:', JSON.stringify(status, null, 2));
    }
  }
  
  console.log('\n📋 Log summary:');
  const wsSends = logs.filter(l => l.includes('WS SEND'));
  const wsRecvs = logs.filter(l => l.includes('WS RECV'));
  const wsOpens = logs.filter(l => l.includes('WS OPENED'));
  console.log(`   WS sends: ${wsSends.length}`);
  wsSends.forEach(l => console.log('   ', l));
  console.log(`   WS receives: ${wsRecvs.length}`);
  wsRecvs.forEach(l => console.log('   ', l));
  console.log(`   WS opens: ${wsOpens.length}`);
  
  await b.close();
  console.log('\n✅ Debug complete');
})();