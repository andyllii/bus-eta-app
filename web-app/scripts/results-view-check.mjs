// Verify the combined ETA / weather / traffic results view renders all three
// data categories with clear visual indicators on a mobile (390x844) layout.
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://localhost:4173';

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

  await page.goto(BASE + '/results?route=1&stop=946C74E30100FE80', {
    waitUntil: 'networkidle',
  });
  await page.waitForSelector('h2', { timeout: 8000 });

  // 1) ETAs present (rows containing a minute / due / 班次 label)
  const etaRows = await page.$$eval('li', (lis) =>
    lis.filter((li) =>
      /分鐘|Due|即將|班次|—/.test(li.textContent || '')
    ).length
  );

  // 2) Weather warning rendered with an icon (svg) and the thunderstorm glyph.
  const weatherSectionHasIcon = await page.$$eval('svg', (svgs) =>
    svgs.length > 0
  );
  const weatherText = await page.evaluate(() => {
    const h2s = Array.from(document.querySelectorAll('h2'));
    const weatherH2 = h2s.find((h) => /Weather/.test(h.textContent || ''));
    if (!weatherH2) return '';
    // walk forward to the section content
    const section = weatherH2.parentElement?.parentElement;
    return section ? section.textContent || '' : '';
  });
  const hasThunderstorm = /Thunderstorm|雷暴/.test(weatherText);

  // 3) Traffic incident rendered with a triangle warning icon + HIGH/MED/LOW tag.
  const incidentText = await page.evaluate(() => {
    const h2s = Array.from(document.querySelectorAll('h2'));
    const incH2 = h2s.find((h) => /Traffic/.test(h.textContent || ''));
    if (!incH2) return '';
    const section = incH2.parentElement?.parentElement;
    return section ? section.textContent || '' : '';
  });
  const hasIncident = /Traffic|交通|Road Incident|道路事故/.test(incidentText);

  // Live ETA "pulse" indicator should be present for live arrivals.
  const livePulse = await page.evaluate(() =>
    !!document.querySelector('span.animate-ping')
  );

  console.log('eta rows rendered       :', etaRows);
  console.log('weather icon present    :', weatherSectionHasIcon);
  console.log('thunderstorm warning    :', hasThunderstorm);
  console.log('traffic incident present:', hasIncident);
  console.log('live ETA pulse indicator:', livePulse);
  console.log('PAGE ERRORS:', errors.length ? errors : 'none');

  const pass =
    etaRows > 0 &&
    weatherSectionHasIcon &&
    hasThunderstorm &&
    hasIncident &&
    livePulse &&
    errors.length === 0;
  console.log('RESULT:', pass ? 'PASS' : 'FAIL');

  await browser.close();
  process.exit(pass ? 0 : 1);
})().catch((e) => {
  console.error('SCRIPT ERROR', e);
  process.exit(2);
});
