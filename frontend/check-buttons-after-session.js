const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(3000);
  
  // Click "New Session"
  const newSessionBtn = await p.$('button:has-text("New Session")');
  if (newSessionBtn) {
    await newSessionBtn.click();
    await p.waitForTimeout(3000);
  }
  
  // Check all buttons now
  const buttons = await p.$$('button');
  console.log('Total buttons after session:', buttons.length);
  for (const btn of buttons) {
    const text = await btn.evaluate(el => el.innerText.trim());
    const title = await btn.evaluate(el => el.getAttribute('title') || '');
    const ariaLabel = await btn.evaluate(el => el.getAttribute('aria-label') || '');
    const disabled = await btn.evaluate(el => el.disabled);
    console.log('BTN:', JSON.stringify({ text, title, aria: ariaLabel, disabled }));
  }
  
  await b.close();
})();