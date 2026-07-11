import { chromium } from 'playwright';
import path from 'node:path';

const MOCKS = '/opt/data/kanban/workspaces/t_b3fe8645/mockups';
const OUT = '/opt/data/kanban/workspaces/t_b3fe8645/design-artifacts';

const screens = [
  { file: '00_flow_diagram.html', name: '00_user_flow', phone: false },
  { file: '01_search.html', name: '01_search', phone: true },
  { file: '02_eta_list.html', name: '02_eta_list', phone: true },
  { file: '03_weather_traffic.html', name: '03_weather_traffic', phone: true },
];

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2 });

for (const s of screens) {
  const url = 'file://' + path.join(MOCKS, s.file);
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(150); // let fonts/layout settle
  if (s.phone) {
    const el = await page.$('.phone');
    await el.screenshot({ path: path.join(OUT, s.name + '.png') });
  } else {
    await page.setViewportSize({ width: 1180, height: 980 });
    await page.waitForTimeout(50);
    await page.screenshot({ path: path.join(OUT, s.name + '.png'), fullPage: true });
  }
  console.log('rendered', s.name);
}

await browser.close();
console.log('done');
