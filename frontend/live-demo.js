const { chromium } = require('playwright');

(async () => {
  // Launch visible browser for the demo
  const b = await chromium.launch({ headless: false, args: ['--no-sandbox', '--window-size=1280,900'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  
  console.log('1. Opening Tektos...');
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(3000);
  await p.screenshot({ path: '/tmp/tektos-1-welcome.png' });
  console.log('   Screenshot: /tmp/tektos-1-welcome.png');
  
  console.log('2. Clicking "New Session"...');
  await p.click('button:has-text("New Session")');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: '/tmp/tektos-2-session.png' });
  console.log('   Screenshot: /tmp/tektos-2-session.png');
  
  console.log('3. Typing coding task...');
  await p.click('textarea, [contenteditable="true"]');
  await p.type('textarea, [contenteditable="true"]', 
    'Create a Python function that implements a binary search tree with insert, delete, and search operations. Include type hints and docstrings.', 
    { delay: 20 });
  await p.screenshot({ path: '/tmp/tektos-3-typed.png' });
  console.log('   Screenshot: /tmp/tektos-3-typed.png');
  
  console.log('4. Sending the task...');
  await p.click('button:has-text("Send"), button:has-text("▶"), button svg:last-child');
  await p.waitForTimeout(5000);
  await p.screenshot({ path: '/tmp/tektos-4-sending.png' });
  console.log('   Screenshot: /tmp/tektos-4-sending.png');
  
  console.log('5. Waiting for response...');
  await p.waitForTimeout(15000);
  await p.screenshot({ path: '/tmp/tektos-5-response.png' });
  console.log('   Screenshot: /tmp/tektos-5-response.png');
  
  // Check connection state
  const state = await p.evaluate(() => ({
    connection: document.body.textContent.match(/connected|disconnected|reconnect|connecting/)?.[0] || 'not found',
    hasMessages: document.querySelectorAll('[class*=message]').length,
    hasStreaming: !!document.querySelector('[class*=streaming], [class*=thinking]')
  }));
  console.log('FINAL STATE:', JSON.stringify(state, null, 2));
  
  console.log('\n🎬 Demo complete! Screenshots saved to /tmp/tektos-*.png');
  console.log('Open them in your browser to see the live stream.');
  
  await b.close();
})();
