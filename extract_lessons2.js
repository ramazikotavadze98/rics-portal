// extract_lessons2.js — uses Playwright to extract Rise 360 lesson structure from DOM
const { chromium } = require('playwright');
const fs = require('fs');

const MODULES = ['403251', '403255', '403267', '403280', '403301', '403312', '403331'];
const BASE = 'http://localhost:8080/rics_FULL';

async function extractModule(page, moduleId) {
  const url = BASE + '/' + moduleId + '/scormcontent/index.html';
  console.log('\n=== Module ' + moduleId + ' ===');

  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(5000);

  const result = await page.evaluate(function() {
    var out = { title: document.title, structure: [], navText: '', riseKeys: [] };

    // Check window.Rise
    try {
      if (window.Rise) {
        out.riseKeys = Object.keys(window.Rise);
        var course = window.Rise.course;
        if (course) {
          out.courseTitle = course.title;
          var lessons = course.lessons || course.chapters;
          if (lessons) {
            out.structure = lessons.map(function(l) {
              return { id: l.id, title: l.title, type: l.type };
            });
          }
        }
      }
    } catch(e) { out.riseErr = String(e); }

    // Fallback: get full body text split by lines
    if (out.structure.length === 0) {
      // Get nav sidebar text
      var navEl = document.querySelector('nav') ||
                  document.querySelector('[class*="coursenav"]') ||
                  document.querySelector('[class*="CourseNav"]') ||
                  document.querySelector('[class*="sidebar"]') ||
                  document.querySelector('aside');
      if (navEl) {
        out.navText = navEl.innerText || navEl.textContent;
      } else {
        // Get all visible text content and look for lesson-like lines
        out.navText = document.body.innerText || document.body.textContent;
      }
    }

    // Also expose window.__fetchCourse result
    try {
      if (window.__fetchCourse) {
        var fc = window.__fetchCourse;
        out.fetchCourseType = typeof fc;
        if (typeof fc === 'object') {
          out.fetchCourseKeys = Object.keys(fc);
        }
      }
    } catch(e) {}

    // Get all class names that contain "lesson" or "nav" or "chapter"
    var relevant = Array.from(document.querySelectorAll('*')).filter(function(el) {
      var cn = (typeof el.className === 'string') ? el.className : '';
      return cn.match(/lesson|nav|chapter|sidebar|course/i);
    });
    out.relevantElements = relevant.slice(0, 20).map(function(el) {
      return {
        tag: el.tagName,
        cls: (typeof el.className === 'string') ? el.className.substring(0, 80) : '',
        text: el.textContent.trim().substring(0, 60)
      };
    });

    return out;
  });

  console.log('  Title: ' + result.title);
  console.log('  Rise keys: ' + result.riseKeys.join(', '));
  if (result.riseErr) console.log('  Rise err: ' + result.riseErr);
  if (result.fetchCourseType) console.log('  fetchCourse type: ' + result.fetchCourseType + ' keys: ' + (result.fetchCourseKeys || []).join(', '));

  if (result.structure.length > 0) {
    console.log('  LESSONS from Rise.course (' + result.structure.length + '):');
    result.structure.forEach(function(l) {
      console.log('    [' + (l.type || '?') + '] ' + l.title);
    });
  } else {
    console.log('  Relevant elements:');
    result.relevantElements.forEach(function(el) {
      console.log('    <' + el.tag + ' class="' + el.cls + '"> ' + el.text);
    });
    if (result.navText) {
      var lines = result.navText.split('\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 2 && l.length < 100; });
      console.log('  Nav lines (' + lines.length + '):');
      lines.slice(0, 40).forEach(function(l) { console.log('    ' + l); });
    }
  }

  return result;
}

(async function() {
  var browser = await chromium.launch({ headless: true });
  var context = await browser.newContext();
  var page = await context.newPage();
  page.on('console', function(msg) {});  // suppress

  var allResults = {};
  // Test first module only
  for (var i = 0; i < 1; i++) {
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
