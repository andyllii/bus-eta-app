// Render the running web app in a mobile viewport and assert key UI is present,
// then exercise the live API by navigating to a results URL.
import path from 'path';

import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://localhost:5173';

(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROME_PATH ||
      '/opt/data/kanban/workspaces/t_b3fe8645/transportation-app/.pw-browsers/chromium_headless_shell-1228/chrome-linux/headless_shell',
  });
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, // iPhone 12/13/14 logical size
    isMobile: true,
    deviceScaleFactor: 3,
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push('console: ' + m.text());
  });

  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  const title = await page.textContent('h1');
  const hasSearch = await page.$('input[type="search"]');
  const hasChips = await page.$$eval('button', (bs) =>
    bs.some((b) => b.textContent && b.textContent.includes('路線'))
  );

  console.log('mobile title:', JSON.stringify(title));
  console.log('search input present:', !!hasSearch);
  console.log('route quick-pick chips present:', hasChips);

  // Exercise the live API: open a results view for route 1.
  await page.goto(BASE + '/results?route=1&stop=946C74E30100FE80', {
    waitUntil: 'networkidle',
  });
  // Wait for the ETA board header or a friendly empty state.
  await page.waitForSelector('h2', { timeout: 8000 });
  const boardHeading = await page.textContent('h2');
  const etas = await page.$$eval('li', (lis) =>
    lis.filter((li) =>
      /分鐘|Due|即將|班次|—/.test(li.textContent || '')
    ).length
  );

  console.log('results heading:', JSON.stringify(boardHeading));
  console.log('eta rows rendered:', etas);

  const pass =
    !!title && !!hasSearch && hasChips && !!boardHeading && etas > 0 && errors.length === 0;
  console.log('PAGE ERRORS:', errors.length ? errors : 'none');
  console.log('RESULT:', pass ? 'PASS' : 'FAIL');

  await browser.close();
  process.exit(pass ? 0 : 1);
})().catch((e) => {
  console.error('SCRIPT ERROR', e);
  process.exit(2);
});
