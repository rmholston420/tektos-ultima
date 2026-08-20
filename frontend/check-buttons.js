const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(3000);
  
  const buttons = await p.$$('button');
  console.log('Total buttons:', buttons.length);
  for (const btn of buttons) {
    const text = await btn.evaluate(el => el.innerText.trim());
    const title = await btn.evaluate(el => el.getAttribute('title') || '');
    const ariaLabel = await btn.evaluate(el => el.getAttribute('aria-label') || '');
    console.log('BTN:', JSON.stringify({ text, title, aria: ariaLabel }));
  }
  
  await b.close();
})();