const { chromium } = require('playwright');
const fs = require('fs');

const MODULES = ['403251', '403255', '403267', '403280', '403301', '403312', '403331'];
const BASE = 'http://localhost:8080/rics_FULL';

async function extractModule(page, moduleId) {
  const url = `${BASE}/${moduleId}/scormcontent/index.html`;
  console.log(`\n=== Module ${moduleId} ===`);
  console.log(`Loading: ${url}`);

  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

  
  try {
    await page.waitForSelector('[class*="nav"], [class*="lesson"], [class*="sidebar"], [class*="menu"], nav', {
      timeout: 15000
    });
  } catch (e) {
    console.log('  Sidebar not found within timeout, dumping page structure...');
  }

  await page.waitForTimeout(3000);

  // Extract navigation structure from DOM
  const result = await page.evaluate(() => {
    const items = [];
 
    
    const selectors = [
      '[data-lesson-id]',
      '[class*="LessonItem"]',
      '[class*="lessonItem"]', 
      '[class*="NavItem"]',
      '[class*="navItem"]',
      '[class*="lesson-item"]',
      '[class*="nav-item"]',
      '.lesson',
      '.chapter',
    ];

    for (const sel of selectors) {
      const els = document.querySelectorAll(sel);
      if (els.length > 0) {
        els.forEach(el => {
          items.push({
            selector: sel,
            text: el.textContent.trim().substring(0, 100),
            tag: el.tagName,
            id: el.id,
            classes: el.className,
            dataAttrs: Object.fromEntries(
              Array.from(el.attributes)
                .filter(a => a.name.startsWith('data-'))
                .map(a => [a.name, a.value])
            )
          });
        });
        break;
      }
    }

    // Strategy 2: Dump all nav/aside elements
    if (items.length === 0) {
      const navEls = document.querySelectorAll('nav, aside, [role="navigation"]');
      navEls.forEach(el => {
        items.push({
          selector: 'nav/aside',
          text: el.textContent.trim().substring(0, 500),
          tag: el.tagName,
          classes: el.className,
        });
      });
    }

    // Strategy 3: Get the entire body text structure
    if (items.length === 0) {
      items.push({
        selector: 'body-fallback',
        text: document.body.textContent.trim().substring(0, 2000),
        tag: 'BODY',
        classes: document.body.className,
      });
    }

    // Also try to find the React root data
    const reactRoot = document.getElementById('root') || document.getElementById('app') || document.querySelector('[id*="app"]');
    
    return {
      title: document.title,
      url: window.location.href,
      items: items,
      bodyClasses: document.body.className,
      allClassNames: Array.from(new Set(
        Array.from(document.querySelectorAll('*')).map(el => el.className).filter(c => typeof c === 'string' && c.length > 0)
      )).slice(0, 50),
      reactRoot: reactRoot ? reactRoot.innerHTML.substring(0, 500) : null,
      windowKeys: Object.keys(window).filter(k => k.toLowerCase().includes('course') || k.toLowerCase().includes('lesson') || k.toLowerCase().includes('rise')),
    };
  });

  console.log(`  Title: ${result.title}`);
  console.log(`  Items found: ${result.items.length}`);
  console.log(`  Window course keys: ${result.windowKeys}`);
  
  if (result.items.length > 0 && result.items[0].selector !== 'body-fallback') {
    result.items.forEach((item, i) => {
      console.log(`  [${i}] ${item.text.substring(0, 80)}`);
    });
  } else {
    console.log(`  Body classes: ${result.bodyClasses}`);
    console.log(`  Sample class names: ${result.allClassNames.slice(0, 10).join(', ')}`);
    if (result.reactRoot) {
      console.log(`  React root preview: ${result.reactRoot.substring(0, 300)}`);
    }
  }

  return result;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Suppress console errors
  page.on('console', msg => {
    if (msg.type() === 'error') return;
  });

  const allResults = {};

  // Just do first module to understand structure
  for (const mod of MODULES.slice(0, 1)) {
    try {
      allResults[mod] = await extractModule(page, mod);
    } catch (e) {
      console.log(`  ERROR: ${e.message}`);
    }
  }

  await browser.close();

  // Save full results
  fs.writeFileSync('C:\\Users\\user\\lesson_structure.json', JSON.stringify(allResults, null, 2));
  console.log('\nSaved to lesson_structure.json');
})();
