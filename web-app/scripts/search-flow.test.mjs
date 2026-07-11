// Acceptance test for the bus route/stop Search view.
//
// Drives the REAL search flow end-to-end on a 375px-wide mobile viewport:
//   1. type a query into the search box
//   2. the app calls GET /api/v1/search (live backend via Vite proxy)
//   3. results render as a list
//   4. tapping a result navigates to /results with the correct id
//   5. the results screen then loads real ETA data
//
// This is what the spec's acceptance criterion ("search returns results from
// API and routes correctly to results view on a 375px viewport") requires —
// the generic render-check only loaded /results directly and used 390px.
//
// Run: node scripts/search-flow.test.mjs  (needs `npm run dev` on :5173, or
// pass BASE=http://localhost:4173 when served via `npm run preview`)
import path from 'path';

import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://localhost:5173';
const CHROME =
  process.env.CHROME_PATH ||
  '/opt/data/kanban/workspaces/t_b3fe8645/transportation-app/.pw-browsers/chromium_headless_shell-1228/chrome-linux/headless_shell';

let failures = 0;
function step(ok, msg) {
  if (ok) {
    console.log('  ✓ ' + msg);
  } else {
    console.error('  ✗ ' + msg);
    failures++;
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  // iPhone SE / small Android logical width = 375px.
  const ctx = await browser.newContext({
    viewport: { width: 375, height: 667 },
    isMobile: true,
    deviceScaleFactor: 2,
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push('console: ' + m.text());
  });

  // --- Warm up the /results route first ---
  // The first transform of the lazily-imported ResultsScreen can be slow under
  // Vite dev. Touch the route once (discard the page) so the SPA click later
  // never races a cold module compile and the waitForSelector doesn't flake.
  const warm = await ctx.newPage();
  await warm.goto(BASE + '/results?route=1', { waitUntil: 'networkidle' });
  await warm.waitForSelector('h2', { timeout: 15000 }).catch(() => {});
  await warm.close();

  // --- Load the search view ---
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  const input = await page.$('[data-testid="search-input"]');
  step(!!input, 'search input is present at 375px viewport');

  // --- Type a query and wait for live results ---
  await page.fill('[data-testid="search-input"]', '1');
  await page.waitForSelector('[data-testid="search-result"]', { timeout: 8000 });
  const resultCount = await page.$$eval(
    '[data-testid="search-result"]',
    (els) => els.length
  );
  step(resultCount > 0, `live search returned ${resultCount} result(s) from API`);

  // Capture the first result's identity for the routing assertion.
  const first = await page.$eval('[data-testid="search-result"]', (el) => ({
    kind: el.getAttribute('data-kind'),
    id: el.getAttribute('data-id'),
  }));
  step(
    !!first.kind && !!first.id,
    `first result carries id=${first.id} (${first.kind})`
  );

  // --- Tap the result and confirm correct routing to /results ---
  await page.click('[data-testid="search-result"]');
  await page.waitForFunction(
    () => location.pathname === '/results',
    { timeout: 5000 }
  );
  const url = new URL(page.url());
  const expectedParam = first.kind === 'route' ? 'route' : 'stop';
  step(
    url.searchParams.get(expectedParam) === first.id,
    `navigated to /results?${expectedParam}=${first.id} (got ${url.searchParams.get(
      expectedParam
    )})`
  );

  // --- Results screen renders real data (ETA board header appears) ---
  // The SPA already navigated here via the click above; the board data loads
  // from the live backend. Wait for the rendered heading.
  await page.waitForSelector('h2', { timeout: 15000 });
  const heading = (await page.textContent('h2')) || '';
  step(!!heading.trim(), `results view rendered a section heading: ${JSON.stringify(heading.trim())}`);

  // --- No horizontal overflow on 375px (layout fits small screens) ---
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  step(overflow <= 1, `no horizontal overflow at 375px (overflowX=${overflow}px)`);

  step(errors.length === 0, `no page/console errors (${errors.length})`);

  // --- Second scenario: a STOP result must route with stop=<id> ---
  const page2 = await ctx.newPage();
  const errs2 = [];
  page2.on('pageerror', (e) => errs2.push(String(e)));
  await page2.goto(BASE + '/', { waitUntil: 'networkidle' });
  // "plaza" matches a stop (Cheung Sha Wan Plaza) on the live backend.
  await page2.fill('[data-testid="search-input"]', 'plaza');
  await page2.waitForSelector('[data-testid="search-result"]', { timeout: 8000 });
  // Pick the first STOP-kind result.
  const stopHandle = await page2.waitForSelector(
    '[data-testid="search-result"][data-kind="stop"]',
    { timeout: 8000 }
  );
  const stopId = await stopHandle.getAttribute('data-id');
  await stopHandle.click();
  await page2.waitForFunction(() => location.pathname === '/results', {
    timeout: 5000,
  });
  const url2 = new URL(page2.url());
  step(
    url2.searchParams.get('stop') === stopId,
    `stop result routed to /results?stop=${stopId} (got ${url2.searchParams.get('stop')})`
  );
  step(errs2.length === 0, `stop-scenario no errors (${errs2.length})`);

  await page2.close();
  await browser.close();
  console.log(
    `\n${failures === 0 ? 'SEARCH FLOW: PASS (route + stop scenarios)' : `SEARCH FLOW: ${failures} FAILURE(S)`}`
  );
  if (errors.length) console.log('ERRORS:', errors);
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => {
  console.error('SCRIPT ERROR', e);
  process.exit(2);
});
