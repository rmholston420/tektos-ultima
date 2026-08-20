const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  await p.goto('http://localhost:3003');
  await p.waitForTimeout(4000);

  const state = await p.evaluate(() => ({
    title: document.title,
    connection: document.body.textContent.match(/connected|disconnected|reconnect|connecting/)?.[0] || 'not found',
    hasSidebar: !!document.querySelector('aside, [class*=sidebar]'),
    hasChat: !!document.querySelector('[class*=chat], [class*=composer], [class*=welcome]'),
    buttonCount: document.querySelectorAll('button').length,
    bodyLength: document.body.textContent.length
  }));
  console.log('STATE:', JSON.stringify(state, null, 2));

  const buttons = await p.$$eval('button', els =>
    els.map(e => e.textContent.trim().split('\n')[0].substring(0, 30)).filter(Boolean)
  );
  console.log('BUTTONS:', JSON.stringify(buttons));

  await p.screenshot({ path: '/tmp/tektos-gui.png', fullPage: false });
  console.log('SAVED: /tmp/tektos-gui.png');

  await b.close();
})();
