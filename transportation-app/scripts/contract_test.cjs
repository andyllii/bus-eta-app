/**
 * Functional contract test: exercises the REAL client modules (api.ts +
 * i18n.tsx) against a realistic backend payload (the EtaAggregate shape
 * returned by GET /api/v1/eta) and asserts the runtime contract the app
 * relies on:
 *
 *   1. Text fields resolve to plain strings (never "[object Object]").
 *   2. snake_case keys are mapped to camelCase (serviceType, etaSeq, query,
 *      degraded, ...).
 *   3. ETA live/scheduled status is derived from the remark.
 *   4. ApiError is thrown with code+message on a non-OK response.
 *   5. The primary endpoint path is /api/v1/eta?route=&stop=.
 *
 * Run: node scripts/contract_test.cjs
 */
const path = require('path');

const appDir = path.resolve(__dirname, '..');
const compiled = path.join(appDir, '.out-test');
const { getEta, checkRouteStop } = require(path.join(compiled, 'api.js'));
const { resolveText, etaLiveStatus } = require(path.join(compiled, 'i18n.js'));
const { ApiError } = require(path.join(compiled, 'types.js'));

// A faithful snapshot of the live /api/v1/eta shape (lang=en), captured from
// the running API in mock mode.
const BACKEND_PAYLOAD = {
  query: { route: '1', stop_id: '946C74E30100FE80', operator: 'KMB', lang: 'en' },
  etas: [
    {
      co: 'KMB',
      route: '1',
      direction: 'O',
      service_type: 1,
      seq: 12,
      dest: { en: 'Central (Macao Ferry)', tc: '中環（港澳碼頭）', sc: '中环（港澳码头）' },
      eta_seq: 1,
      eta: '2026-07-10T08:49:00Z',
      minutes_remaining: 4,
      remark: { en: 'Scheduled', tc: '預定', sc: '预定' },
    },
    {
      co: 'KMB',
      route: '1',
      direction: 'O',
      service_type: 1,
      seq: 12,
      dest: { en: 'Central (Macao Ferry)', tc: '中環（港澳碼頭）', sc: '中环（港澳码头）' },
      eta_seq: 2,
      eta: '2026-07-10T09:00:00Z',
      minutes_remaining: 15,
      remark: null,
    },
  ],
  weather: {
    temperature: { place: 'Hong Kong Observatory', value: 28, unit: 'C' },
    description: 'Light Rain',
    icon: [65],
    warnings: [
      {
        code: 'WTSTORM',
        title: { en: 'Thunderstorm Warning', tc: '雷暴警告', sc: '雷暴警告' },
        severity: 'amber',
      },
    ],
  },
  incidents: [
    {
      id: 'TD20260710-00123',
      heading: { en: 'Road blocked due to accident', tc: '因交通意外道路封閉', sc: '因交通意外道路封闭' },
      location: { en: 'Cheung Sha Wan Road', tc: '長沙灣道', sc: '长沙湾道' },
      relevance: 'high',
    },
  ],
  query_time: '2026-07-10T08:40:00Z',
  degraded: false,
};

let failures = 0;
function check(name, cond, extra) {
  if (cond) {
    console.log('  ok  -', name);
  } else {
    console.error('  FAIL-', name, extra != null ? JSON.stringify(extra) : '');
    failures++;
  }
}

// Stub global fetch so we control the wire response precisely.
global.fetch = async (url) => {
  if (url.includes('DEADBEEF')) {
    return {
      ok: false,
      status: 404,
      json: async () => ({ code: 'RESOURCE_NOT_FOUND', message: 'No ETA data for route 1 at stop DEADBEEF.' }),
    };
  }
  if (url.includes('/api/v1/eta')) {
    return {
      ok: true,
      status: 200,
      json: async () => BACKEND_PAYLOAD,
    };
  }
  return { ok: false, status: 404, json: async () => ({ code: 'RESOURCE_NOT_FOUND', message: 'Not found.' }) };
};

(async () => {
  const agg = await getEta('1', '946C74E30100FE80', 'en');

  // 1. Multilingual text resolves to a string, not [object Object].
  check('query.stopId mapped from stop_id', agg.query.stopId === '946C74E30100FE80');
  check('eta.dest resolves to string', resolveText(agg.etas[0].dest, 'en') === 'Central (Macao Ferry)');
  check('incident.heading resolves to string', resolveText(agg.incidents[0].heading, 'en') === 'Road blocked due to accident');
  check('weather.warning.title resolves to string', resolveText(agg.weather.warnings[0].title, 'en') === 'Thunderstorm Warning');
  check('no [object Object] in eta dest', !String(resolveText(agg.etas[0].dest, 'tc')).includes('object'));

  // 2. snake_case -> camelCase key mapping.
  check('serviceType mapped from service_type', agg.etas[0].serviceType === 1);
  check('etaSeq mapped from eta_seq', agg.etas[0].etaSeq === 1);
  check('queryTime mapped from query_time', agg.queryTime === '2026-07-10T08:40:00Z');
  check('eta remains ISO string', agg.etas[0].eta === '2026-07-10T08:49:00Z');
  check('degraded mapped from degraded', agg.degraded === false);

  // 3. live/scheduled derived from remark.
  check('remark "Scheduled" -> scheduled', etaLiveStatus('Scheduled') === 'scheduled');
  check('remark with 實時 -> live', etaLiveStatus('實時到站') === 'live');

  // 4. tc fallback works when requested lang missing.
  const onlyTc = { en: null, tc: '深水埗', sc: null };
  check('tc fallback when en null', resolveText(onlyTc, 'en') === '深水埗');

  // 5. ApiError on non-OK (unknown route/stop -> 404).
  let threw = null;
  try {
    await getEta('1', 'DEADBEEF', 'en');
  } catch (e) {
    threw = e;
  }
  check('404 raises ApiError with code', threw instanceof ApiError && threw.status === 404 && threw.code === 'RESOURCE_NOT_FOUND');

  // 6. checkRouteStop returns false on 404, true on 200.
  const bad = await checkRouteStop('1', 'DEADBEEF', 'en');
  check('checkRouteStop false on 404', bad === false);
  const good = await checkRouteStop('1', '946C74E30100FE80', 'en');
  check('checkRouteStop true on 200', good === true);

  console.log(failures === 0 ? '\nALL PASSED' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
