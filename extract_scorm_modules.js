
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = 'http://localhost:8080';
const MODULES = ['403255', '403267'];

const MOCK_SCORM_SCRIPT = `
(function() {
  var store = {};
  window.API = {
    LMSInitialize: function() { return "true"; },
    LMSFinish: function() { return "true"; },
    LMSGetValue: function(k) { return store[k] || ""; },
    LMSSetValue: function(k, v) { store[k] = v; return "true"; },
    LMSCommit: function() { return "true"; },
    LMSGetLastError: function() { return "0"; },
    LMSGetErrorString: function() { return "No Error"; },
    LMSGetDiagnostic: function() { return ""; }
  };
  window.API_1484_11 = {
    Initialize: function() { return "true"; },
    Terminate: function() { return "true"; },
    GetValue: function(k) { return store[k] || ""; },
    SetValue: function(k, v) { store[k] = v; return "true"; },
    Commit: function() { return "true"; },
    GetLastError: function() { return 0; },
    GetErrorString: function() { return "No Error"; },
    GetDiagnostic: function() { return ""; }
  };
  console.log('[mock] SCORM API injected');
})();
`;

async function extractModule(browser, moduleId) {
  const url = `${BASE}/rics_FULL/${moduleId}/scormcontent/index.html`;
  console.log(`\n=== Module ${moduleId} ===`);
  console.log(`  Loading: ${url}`);

  const context = await browser.newContext();
  const page = await context.newPage();

  await page.addInitScript(MOCK_SCORM_SCRIPT);

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(4000);

  // Check for error
  const bodyText = await page.evaluate(() => document.body.innerText.trim());
  if (bodyText.includes('outside of a supported LMS')) {
    console.log('  Still shows LMS error — trying parent window injection...');
    // Try evaluating the mock in the page directly
    await page.evaluate(MOCK_SCORM_SCRIPT);
    await page.waitForTimeout(3000);
    const bodyText2 = await page.evaluate(() => document.body.innerText.trim());
    console.log('  Body after injection:', bodyText2.substring(0, 100));
  }

  // Try to click the first visible lesson/start button
  const coverItems = await page.$$('[class*="lesson-progress"], [class*="lesson-cover"], [class*="cover-lesson"]');
  console.log(`  Found ${coverItems.length} cover items`);
  
  // Try clicking any clickable element on the course cover
  try {
    const clicked = await page.evaluate(() => {
      const selectors = [
        '[class*="lesson-progress"]',
        '[class*="cover-lesson"]', 
        '[class*="lesson-link"]',
        'a[href*="lesson"]',
        '[class*="course-cover"] a',
        '[class*="lesson-tile"]',
        'button[class*="lesson"]'
      ];
      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          el.click();
          return sel;
        }
      }
      // fallback: click first link
      const links = document.querySelectorAll('a');
      if (links.length > 0) { links[0].click(); return 'first-link'; }
      return null;
    });
    console.log(`  Clicked: ${clicked}`);
    await page.waitForTimeout(3000);
  } catch(e) {
    console.log(`  Click error: ${e.message}`);
  }

  // Extract course nav
  const navEl = await page.$('[class*="course-nav"]');
  let navText = '';
  let navHTML = '';
  
  if (navEl) {
    navText = await navEl.evaluate(el => el.innerText);
    navHTML = await navEl.evaluate(el => el.outerHTML.substring(0, 2000));
    console.log(`  Nav found! Lines: ${navText.split('\n').filter(l => l.trim()).length}`);
  } else {
    console.log('  No nav found. Body text:', bodyText.substring(0, 150));
  }

  const result = {
    navText,
    navHTML,
    bodyText: bodyText.substring(0, 500)
  };

  await context.close();
  return result;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  
  // Load existing structure
  let structure = {};
  if (fs.existsSync('lesson_structure.json')) {
    structure = JSON.parse(fs.readFileSync('lesson_structure.json', 'utf8'));
  }

  for (const moduleId of MODULES) {
    try {
      const result = await extractModule(browser, moduleId);
      if (!structure[moduleId]) structure[moduleId] = {};
      structure[moduleId].navText = result.navText;
      structure[moduleId].navHTML = result.navHTML;
      structure[moduleId].bodyText = result.bodyText;
    } catch (err) {
      console.error(`  ERROR: ${err.message}`);
    }
  }

  fs.writeFileSync('lesson_structure.json', JSON.stringify(structure, null, 2));
  console.log('\nDone. lesson_structure.json updated.');
  await browser.close();
})();
