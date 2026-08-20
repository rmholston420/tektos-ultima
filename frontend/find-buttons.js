const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(2000);
  await p.click('button:has-text("New Session")');
  await p.waitForTimeout(1500);
  
  const buttons = await p.$$eval('button', els => 
    els.map(e => ({
      text: e.textContent.trim().substring(0,50),
      class: e.className.substring(0,80),
      type: e.type
    }))
  );
  console.log('BUTTONS:', JSON.stringify(buttons, null, 2));
  
  await b.close();
})();
