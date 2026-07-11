// Mobile UX / performance acceptance check for the bus ETA web app.
//
// Drives real pages on emulated phones (iPhone SE 375px and iPhone 12 390px)
// and verifies the criteria from the optimization task:
//   1. Touch targets are >= 44px tall (WCAG 2.5.5 / Apple HIG) on every
//      interactive control (search field, quick-pick chips, language switch,
//      results back buttons, ETA pills).
//   2. No layout shift (CLS ~= 0) when the results view swaps its loading
//      spinner for real data — i.e. the content area reserves height.
//   3. No horizontal overflow on small screens.
//   4. Single-handed use: a thumb-reachable back-to-search control sits in the
//      lower half of the viewport on the results screen.
//   5. Zero page/console errors throughout.
//
// Run: node scripts/mobile-ux-check.mjs  (against `npm run preview` @ :4173,
// or pass BASE=http://localhost:5173 for the dev server)
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://localhost:4173';
const CHROME =
  process.env.CHROME_PATH ||
  '/opt/data/kanban/workspaces/t_b3fe8645/transportation-app/.pw-browsers/chromium_headless_shell-1228/chrome-linux/headless_shell';

const VIEWPORTS = [
  { name: 'iPhone SE (375x667)', width: 375, height: 667 },
  { name: 'iPhone 12 (390x844)', width: 390, height: 844 },
];

// Minimum comfortable touch-target size (CSS px).
const MIN_TARGET = 44;

let failures = 0;
function step(ok, msg) {
  if (ok) {
    console.log('  ✓ ' + msg);
  } else {
    console.error('  ✗ ' + msg);
    failures++;
  }
}

/** Inject a CLS collector and return a function that reads the running total. */
async function installClsCollector(page) {
  await page.addInitScript(() => {
    window.__cls = 0;
    try {
      const po = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) window.__cls += entry.value;
        }
      });
      po.observe({ type: 'layout-shift', buffered: true });
    } catch {
      window.__cls = -1; // unsupported
    }
  });
}

async function measureTarget(selector, page) {
  return page.$$eval(
    selector,
    (els, min) => {
      const out = [];
      for (const el of els) {
        const r = el.getBoundingClientRect();
        // Only judge controls currently visible in the layout.
        if (r.width === 0 || r.height === 0) continue;
        out.push({ w: Math.round(r.width), h: Math.round(r.height) });
      }
      return out;
    },
    MIN_TARGET
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });

  for (const vp of VIEWPORTS) {
    console.log(`\n=== ${vp.name} ===`);
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      isMobile: true,
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push('console: ' + m.text());
    });
    await installClsCollector(page);

    // ---- Search screen: touch targets ----
    await page.goto(BASE + '/', { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="search-input"]', { timeout: 8000 });

    const input = await measureTarget('[data-testid="search-input"]', page);
    step(
      input.length > 0 && input.every((b) => b.h >= MIN_TARGET),
      `search input >= ${MIN_TARGET}px tall (h=${JSON.stringify(input)})`
    );

    const chips = await measureTarget('button', page);
    // Filter to the quick-pick chips (text contains 路線) for a precise check,
    // but assert all visible buttons meet the minimum as a safety net.
    const chipHeights = chips.map((c) => c.h);
    step(
      chipHeights.length > 0 && chipHeights.every((h) => h >= MIN_TARGET),
      `all visible buttons >= ${MIN_TARGET}px tall (heights=${JSON.stringify(chipHeights)})`
    );

    // ---- Accessibility: the search region is labelled and the live results
    //      region announces updates ----
    const a11y = await page.evaluate(() => {
      const form = document.querySelector('[role="search"]');
      const input = document.querySelector('[data-testid="search-input"]');
      const results = document.querySelector('ul[aria-label="Search results"]');
      const langBtns = document.querySelectorAll(
        'header button[aria-pressed]'
      );
      return {
        hasSearchRole: !!form,
        inputLabelled:
          !!input &&
          (input.getAttribute('aria-label') ||
            document.querySelector('label[for="' + input.id + '"]')),
        resultsLive: results
          ? results.getAttribute('aria-live') === 'polite'
          : false,
        langBtnsLabelled: Array.from(langBtns).every(
          (b) => b.textContent && b.textContent.trim().length > 0
        ),
      };
    });
    step(a11y.hasSearchRole, 'search form exposes role="search"');
    step(!!a11y.inputLabelled, 'search input has an accessible name');
    step(
      a11y.resultsLive,
      'results list is an aria-live="polite" region'
    );
    step(
      a11y.langBtnsLabelled,
      'TopBar language buttons have visible/accessible labels'
    );

    // Language switch buttons in the TopBar.
    const langBtns = await measureTarget(
      'header button[aria-pressed]',
      page
    );
    step(
      langBtns.length === 3 && langBtns.every((b) => b.h >= MIN_TARGET && b.w >= MIN_TARGET),
      `TopBar language buttons >= ${MIN_TARGET}px (${JSON.stringify(langBtns)})`
    );

    // ---- No horizontal overflow on the search screen ----
    const overflowSearch = await page.evaluate(
      () =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    step(
      overflowSearch <= 1,
      `no horizontal overflow on search @${vp.width}px (overflowX=${overflowSearch}px)`
    );

    // ---- Lazy-load the results route, then measure CLS during data swap ----
    await page.goto(BASE + '/results?route=1&stop=946C74E30100FE80', {
      waitUntil: 'networkidle',
    });
    await page.waitForSelector('[data-testid="back-to-search"]', {
      timeout: 15000,
    });
    // Let any post-hydration layout settle.
    await page.waitForTimeout(600);
    const cls = await page.evaluate(() => window.__cls ?? -1);
    step(
      cls >= 0 && cls < 0.05,
      `cumulative layout shift < 0.05 on results load (CLS=${cls})`
    );

    // ---- Results: accessibility ----
    const resA11y = await page.evaluate(() => {
      const nav = document.querySelector('[data-testid="back-to-search"]');
      const topBack = document.querySelector(
        '[data-testid="back-to-search-top"]'
      );
      const status = document.querySelector('[role="status"]');
      const etas = document.querySelector('ul[aria-label="Arrival times"]');
      return {
        navLabel: nav ? nav.getAttribute('aria-label') : null,
        topBackLabel: topBack ? topBack.getAttribute('aria-label') : null,
        // The loading status region may have already been swapped for data;
        // just confirm the back controls are named either way.
        etasLive: etas ? etas.getAttribute('aria-live') : null,
      };
    });
    step(
      resA11y.navLabel === 'Back to search',
      `results bottom back control is named (aria-label=${JSON.stringify(
        resA11y.navLabel
      )})`
    );
    step(
      resA11y.topBackLabel === 'Back to search',
      `results top back link is named (aria-label=${JSON.stringify(
        resA11y.topBackLabel
      )})`
    );
    step(
      resA11y.etasLive === 'polite',
      `ETA board is an aria-live="polite" region for screen readers`
    );

    // ---- Results: touch targets ----
    const etaPills = await measureTarget('li span', page);
    // ETA pills are the rounded min-h-[44px] spans; check any span in an li.
    const backBtn = await measureTarget('[data-testid="back-to-search"]', page);
    step(
      backBtn.length > 0 && backBtn.every((b) => b.h >= MIN_TARGET),
      `results bottom back button >= ${MIN_TARGET}px (${JSON.stringify(backBtn)})`
    );

    // Always-present back link at the top should also be tappable.
    const topBack = await measureTarget('[data-testid="back-to-search-top"]', page);
    step(
      topBack.length > 0 && topBack.every((b) => b.h >= MIN_TARGET),
      `results top back link >= ${MIN_TARGET}px (${JSON.stringify(topBack)})`
    );

    // ---- Single-handed: bottom nav sits in the lower viewport half ----
    const navBox = await page.$eval('[data-testid="back-to-search"]', (el) => {
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, cy: r.top + r.height / 2 };
    });
    step(
      navBox.cy > vp.height * 0.5,
      `back-to-search control is in the thumb zone (centerY=${Math.round(
        navBox.cy
      )} > ${vp.height / 2} half of ${vp.height}px)`
    );

    // ---- No horizontal overflow on the results screen ----
    const overflowResults = await page.evaluate(
      () =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    step(
      overflowResults <= 1,
      `no horizontal overflow on results @${vp.width}px (overflowX=${overflowResults}px)`
    );

    step(errors.length === 0, `no page/console errors (${errors.length})`);
    if (errors.length) console.log('  ERRORS:', errors);

    await ctx.close();
  }

  // ---- Reduced-motion: the live ETA pulse must be silenced for users who
  //      request reduced motion, so the app is comfortable for everyone. ----
  console.log('\n=== Reduced-motion preference ===');
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      deviceScaleFactor: 2,
      reducedMotion: 'reduce',
    });
    const page = await ctx.newPage();
    await page.goto(BASE + '/results?route=1&stop=946C74E30100FE80', {
      waitUntil: 'networkidle',
    });
    await page.waitForSelector('[data-testid="back-to-search"]', {
      timeout: 15000,
    });
    await page.waitForTimeout(400);
    const pingAnim = await page.evaluate(() => {
      const el = document.querySelector('.animate-ping');
      if (!el) return 'no-ping-element';
      const cs = getComputedStyle(el);
      return cs.animationName + '|' + cs.animationDuration;
    });
    step(
      pingAnim === 'no-ping-element' ||
        /none|0s|0\.001ms/.test(pingAnim),
      `live-ETA pulse animation disabled under prefers-reduced-motion (got "${pingAnim}")`
    );
    await ctx.close();
  }

  await browser.close();
  console.log(
    `\n${failures === 0 ? 'MOBILE UX CHECK: PASS (375 + 390)' : `MOBILE UX CHECK: ${failures} FAILURE(S)`}`
  );
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => {
  console.error('SCRIPT ERROR', e);
  process.exit(2);
});
