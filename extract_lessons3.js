// extract_lessons3.js — extracts full lesson structure from Rise 360 including Part headers
const { chromium } = require('playwright');
const fs = require('fs');

const MODULES = ['403251', '403255', '403267', '403280', '403301', '403312', '403331'];
const BASE = 'http://localhost:8080/rics_FULL';

async function extractModule(page, moduleId) {
  const url = BASE + '/' + moduleId + '/scormcontent/index.html';
  console.log('\n=== Module ' + moduleId + ' ===');

  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(4000);

  // First: try calling __fetchCourse to get the data
  const courseData = await page.evaluate(function() {
    var out = { lessons: null, raw: null };
    try {
      if (window.__fetchCourse) {
        var result = window.__fetchCourse();
        if (result && typeof result === 'object') {
          out.raw = JSON.stringify(result).substring(0, 5000);
          out.lessons = result;
        }
      }
    } catch(e) { out.err = String(e); }
    return out;
  });

  if (courseData.raw) {
    console.log('  __fetchCourse result: ' + courseData.raw.substring(0, 300));
  }

  // Click into first available lesson to trigger sidebar rendering
  try {
    var firstLesson = await page.$('[class*="lesson-card"], [class*="LessonCard"], .lesson, [data-lesson-id], a[href*="lesson"], button[class*="lesson"]');
    if (!firstLesson) {
      // Try clicking the cover to enter course
      firstLesson = await page.$('a, button, [role="button"]');
    }
    if (firstLesson) {
      await firstLesson.click();
      await page.waitForTimeout(3000);
    }
  } catch(e) {
    console.log('  Click err: ' + e.message);
  }

  // Now extract from the fully rendered lesson view
  const result = await page.evaluate(function() {
    var out = {
      title: document.title,
      structure: [],
      bodyText: '',
    };

    // Get full body text — find lesson/part titles
    var bodyText = document.body.innerText || document.body.textContent || '';
    out.bodyText = bodyText.substring(0, 5000);

    // Find the nav/sidebar specifically
    var navEl = null;
    var selectors = ['[class*="course-nav"]', '[class*="CourseNav"]', '[class*="coursenav"]',
                     'nav', 'aside', '[class*="sidebar"]', '[class*="Sidebar"]',
                     '[class*="lesson-nav"]', '[class*="LessonNav"]'];
    for (var i = 0; i < selectors.length; i++) {
      navEl = document.querySelector(selectors[i]);
      if (navEl) { out.navSelector = selectors[i]; break; }
    }
    if (navEl) {
      out.navHTML = navEl.innerHTML.substring(0, 3000);
      out.navText = (navEl.innerText || navEl.textContent || '').substring(0, 3000);
    }

    // Get all elements with "lesson" or "part" in their class
    var els = document.querySelectorAll('[class*="lesson"], [class*="chapter"], [class*="part-header"], [class*="PartHeader"], [class*="section-header"]');
    out.relevantCount = els.length;
    var seen = new Set();
    var items = [];
    els.forEach(function(el) {
      var t = (el.innerText || el.textContent || '').trim().substring(0, 80);
      if (t && t.length > 2 && !seen.has(t)) {
        seen.add(t);
        items.push({ cls: (typeof el.className === 'string' ? el.className : '').substring(0, 60), text: t });
      }
    });
    out.lessonElements = items.slice(0, 50);

    // Get all PART and section headers
    var allText = document.body.innerHTML;
    var partMatches = allText.match(/PART [A-Z]+ ?[-–] ?[A-Z][^<"]{5,80}/g) || [];
    out.partHeaders = partMatches.slice(0, 20);

    return out;
  });

  console.log('  --- Nav (' + (result.navSelector || 'none') + ') ---');
  if (result.navText) {
    var lines = result.navText.split('\n').map(function(l){return l.trim();}).filter(function(l){return l.length>1;});
    console.log('  Nav lines:');
    lines.slice(0, 40).forEach(function(l){ console.log('    ' + l); });
  } else {
    console.log('  No nav found. Body text:');
    var bodyLines = result.bodyText.split('\n').map(function(l){return l.trim();}).filter(function(l){return l.length>2 && l.length<100;});
    bodyLines.slice(0, 30).forEach(function(l){ console.log('    ' + l); });
  }

  if (result.partHeaders.length > 0) {
    console.log('  PART headers: ' + result.partHeaders.join(' | '));
  }

  return result;
}

(async function() {
  var browser = await chromium.launch({ headless: true });
  var context = await browser.newContext();
  var page = await context.newPage();
  page.on('console', function(msg) {});

  var allResults = {};
  for (var i = 0; i < MODULES.length; i++) {
    var mod = MODULES[i];
    try {
      allResults[mod] = await extractModule(page, mod);
    } catch(e) {
      console.log('  ERROR: ' + e.message);
    }
  }

  await browser.close();
  fs.writeFileSync('C:\\Users\\user\\lesson_structure.json', JSON.stringify(allResults, null, 2));
  console.log('\nSaved to lesson_structure.json');
})();
