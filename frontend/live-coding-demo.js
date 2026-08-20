const { chromium } = require('playwright');

(async () => {
  console.log('🎬 Tektos Coding Demo - Live Stream');
  console.log('====================================\n');
  
  const b = await chromium.launch({ headless: false, args: ['--no-sandbox', '--window-size=1400,900'] });
  const context = await b.newContext({ viewport: { width: 1280, height: 800 } });
  const p = await context.newPage();
  
  // Step 1: Open Tektos
  console.log('Step 1: Opening Tektos...');
  await p.goto('http://localhost:3003');
  await p.waitForLoadState('networkidle');
  await p.waitForTimeout(2000);
  await p.screenshot({ path: '/tmp/tektos-1.png' });
  console.log('   ✓ Welcome screen visible\n');
  
  // Step 2: Create session
  console.log('Step 2: Creating session...');
  await p.click('button:has-text("New Session")');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: '/tmp/tektos-2.png' });
  console.log('   ✓ Session created, composer visible\n');
  
  // Step 3: Type coding task
  console.log('Step 3: Typing coding task...');
  const textarea = p.locator('textarea, [contenteditable="true"]');
  await textarea.waitFor({ state: 'visible' });
  await textarea.click();
  await textarea.pressSequentially('Create a Python function that calculates the factorial of a number using recursion. Add proper error handling for negative numbers.', { delay: 15 });
  await p.screenshot({ path: '/tmp/tektos-3.png' });
  console.log('   ✓ Task typed\n');
  
  // Step 4: Send using Enter key
  console.log('Step 4: Sending message...');
  await textarea.press('Enter');
  await p.waitForTimeout(3000);
  await p.screenshot({ path: '/tmp/tektos-4.png' });
  console.log('   ✓ Message sent\n');
  
  // Step 5: Wait for response
  console.log('Step 5: Waiting for response...');
  await p.waitForTimeout(10000);
  await p.screenshot({ path: '/tmp/tektos-5.png' });
  console.log('   ✓ Response received\n');
  
  // Check state
  const state = await p.evaluate(() => ({
    connection: document.body.textContent?.match(/connected|disconnected|reconnect|connecting/)?.[0] || 'unknown',
    hasMessages: document.querySelectorAll('[class*=message], [class*=transcript]').length,
    hasStreaming: !!document.querySelector('[class*=streaming], [class*=typing], [class*=thinking]'),
    bodyLength: document.body.textContent.length
  }));
  console.log('📊 Final state:', JSON.stringify(state, null, 2));
  console.log('\n🎬 Screenshots saved to /tmp/tektos-{1,2,3,4,5}.png');
  console.log('Open them to see the live coding stream.');
  
  await b.close();
})();
