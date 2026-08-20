const { chromium } = require('playwright');

(async () => {
  console.log('🎬 Tektos Live Coding Demo');
  console.log('============================\n');
  
  const b = await chromium.launch({ 
    headless: false, 
    args: ['--no-sandbox', '--window-size=1280,900'] 
  });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(3000);
  
  console.log('1. Opened Tektos');
  console.log('   Screenshot:', await p.screenshot({ path: '/tmp/tektos-1-welcome.png' }));
  
  // Create a session
  const newSessionBtn = await p.$('button:has-text("New Session")');
  if (newSessionBtn) {
    await newSessionBtn.click();
    await p.waitForTimeout(3000);
    console.log('2. Created session');
    console.log('   Screenshot:', await p.screenshot({ path: '/tmp/tektos-2-session.png' }));
  }
  
  // Check connection
  const connEl = await p.$('.connection-status');
  const connText = connEl ? await connEl.evaluate(el => el.innerText) : 'unknown';
  console.log('   Connection state:', connText);
  
  // Type coding task
  const textarea = await p.$('textarea');
  if (textarea) {
    await textarea.click();
    await textarea.type('Create a Python function that calculates the factorial of a number using recursion. Add proper error handling for negative numbers.', { delay: 30 });
    await p.waitForTimeout(2000);
    console.log('3. Typed coding task');
    console.log('   Screenshot:', await p.screenshot({ path: '/tmp/tektos-3-typed.png' }));
  }
  
  // Click Send
  const sendBtn = await p.$('button[title="Send message"]');
  if (sendBtn) {
    const disabled = await sendBtn.evaluate(el => el.disabled);
    console.log('4. Send button disabled:', disabled);
    
    if (!disabled) {
      await sendBtn.click();
      await p.waitForTimeout(5000);
      console.log('5. Clicked Send');
      console.log('   Screenshot:', await p.screenshot({ path: '/tmp/tektos-4-sending.png' }));
      
      // Check events
      const session = await p.$('[data-session-id]');
      console.log('   Session element found:', !!session);
      
      // Wait for response
      await p.waitForTimeout(10000);
      console.log('6. After waiting for LLM response');
      console.log('   Screenshot:', await p.screenshot({ path: '/tmp/tektos-5-response.png' }));
    } else {
      console.log('   ⚠️ Send button still disabled - checking why');
      
      // Check if session is active
      const sessionStatus = await p.$('.session-status');
      if (sessionStatus) {
        const status = await sessionStatus.evaluate(el => el.innerText);
        console.log('   Session status:', status);
      }
    }
  } else {
    console.log('   ⚠️ Send button not found');
  }
  
  // Get page title and URL
  console.log('\n📊 Final state:');
  console.log('   Title:', await p.title());
  console.log('   URL:', await p.url());
  await b.close();
  console.log('✅ Demo complete');
})();