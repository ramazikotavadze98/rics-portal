const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const moduleId = process.argv[2] || '403255';
  const url = `http://localhost:8080/rics_FULL/${moduleId}/scormdriver/indexAPI.html`;

  console.log('Loading', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(6000);

  console.log('Main page title:', await page.title());
  console.log('Frames:', page.frames().map(f => f.url()));

  for (const frame of page.frames()) {
    try {
      const body = await frame.evaluate(() => document.body ? document.body.innerText.slice(0, 1000) : '');
      const nav = await frame.$('[class*="course-nav"]');
      console.log('\nFRAME URL:', frame.url());
      console.log('BODY:', body);
      if (nav) {
        const navText = await nav.evaluate(el => el.innerText);
        console.log('NAV FOUND:\n', navText);
      }
    } catch (e) {
      console.log('Frame error', e.message);
    }
  }

  await browser.close();
})();
