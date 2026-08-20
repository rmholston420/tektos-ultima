const { chromium } = require('playwright');

(async () => {
  console.log('🎬 Tektos Live Coding Demo - v2');
  console.log('====================================\n');
  
  const b = await chromium.launch({ 
    headless: true, 
    args: ['--no-sandbox'] 
  });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  
  const logs = [];
  p.on('console', msg => {
    const text = msg.text();
    if (!text.includes('React DevTools')) {
      logs.push(`[CONSOLE] ${text}`);
    }
  });
  p.on('requestfailed', req => {
    logs.push(`[FAIL] ${req.url()} ${req.failure().errorText}`);
  });
  
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(3000);
  
  console.log('1. Page loaded');
  await p.screenshot({ path: '/tmp/tektos-1-welcome.png' });
  
  // Create session
  await p.click('button:has-text("New Session")');
  await p.waitForTimeout(2000);
  console.log('2. Session created');
  await p.screenshot({ path: '/tmp/tektos-2-session.png' });
  
  // Wait for WS to connect
  await p.waitForTimeout(2000);
  
  // Type coding task
  const textarea = await p.$('textarea');
  if (textarea) {
    await textarea.click();
    await textarea.type('Create a Python function that calculates the factorial of a number using recursion. Add proper error handling for negative numbers.', { delay: 20 });
    await p.waitForTimeout(1000);
    console.log('3. Typed task');
    await p.screenshot({ path: '/tmp/tektos-3-typed.png' });
  }
  
  // Click Send
  const sendBtn = await p.$('button[title="Send message"]');
  if (sendBtn) {
    const disabled = await sendBtn.evaluate(el => el.disabled);
    console.log(`4. Send button disabled: ${disabled}`);
    
    if (!disabled) {
      await sendBtn.click();
      console.log('5. Clicked Send');
      await p.screenshot({ path: '/tmp/tektos-4-sending.png' });
      
      // Wait for LLM response
      console.log('6. Waiting for LLM response (15s)...');
      await p.waitForTimeout(15000);
      await p.screenshot({ path: '/tmp/tektos-5-response.png' });
      
      const messages = await p.$$('.message-card');
      console.log(`   Messages visible: ${messages.length}`);
      
      // Get streaming content if any
      const assistantMsgs = await p.$$('.message-card-assistant');
      if (assistantMsgs.length > 0) {
        const text = await assistantMsgs[assistantMsgs.length-1].evaluate(el => el.innerText);
        console.log(`   Last assistant content: ${text.substring(0, 300)}...`);
      }
    } else {
      console.log('   ⚠️ Send still disabled');
    }
  }
  
  console.log('\n📋 Logs:');
  logs.forEach(l => console.log(l));
  
  await b.close();
  
  console.log('\n✅ Demo complete');
  console.log('Check /tmp/tektos-{1,2,3,4,5}.png for screenshots');
})();