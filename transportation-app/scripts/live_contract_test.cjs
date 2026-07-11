/**
 * Live end-to-end test: drives the REAL compiled client (api.js) against a
 * running backend (mock or live) and proves the frontend's fetch/normalize
 * chain works against the actual wire contract of the PRIMARY endpoint
 * GET /api/v1/eta?route=&stop=, including the error path.
 *
 *   node scripts/live_contract_test.cjs <baseUrl>
 * Defaults to http://127.0.0.1:8123 (the mock backend launched for verification).
 */
const path = require('path');
const compiled = path.join(__dirname, '..', '.out-test');
const apiMod = require(path.join(compiled, 'api.js'));
const { getEta, checkRouteStop } = apiMod;
const { resolveText, etaLiveStatus } = require(path.join(compiled, 'i18n.js'));
const { ApiError } = require(path.join(compiled, 'types.js'));

const BASE = process.env.EXPO_PUBLIC_API_BASE || process.argv[2] || 'http://127.0.0.1:8123';

process.env.EXPO_PUBLIC_API_BASE = BASE;
// Re-require api.js so it picks up the new base URL.
delete require.cache[require.resolve(path.join(compiled, 'api.js'))];
const { getEta: getEta2 } = require(path.join(compiled, 'api.js'));

let failures = 0;
function check(name, cond, extra) {
  if (cond) console.log('  ok  -', name);
  else { console.error('  FAIL-', name, extra != null ? JSON.stringify(extra) : ''); failures++; }
}

(async () => {
  // 1. Live combined fetch for a known KMB route+stop.
  const c = await getEta2('1', '946C74E30100FE80', 'en');
  check('query.stopId mapped from stop_id', c.query.stopId === '946C74E30100FE80', c.query);
  check('query.operator present', !!c.query.operator, c.query);
  check('etas is an array', Array.isArray(c.etas));
  check('etas have camelCase serviceType', c.etas.every((e) => 'serviceType' in e), c.etas[0]);
  check('etas have camelCase etaSeq', c.etas.every((e) => 'etaSeq' in e), c.etas[0]);
  check('eta.dest resolves to string', resolveText(c.etas[0].dest, 'en').length > 0, c.etas[0] && c.etas[0].dest);
  check('weather present', !!c.weather);
  check('weather.temperature.value is number', typeof c.weather.temperature.value === 'number', c.weather && c.weather.temperature);
  check('incidents is array', Array.isArray(c.incidents));
  check('incidents carry relevance', c.incidents.every((i) => 'relevance' in i), c.incidents[0]);
  check('queryTime mapped from query_time', typeof c.queryTime === 'string' && c.queryTime.length > 0, c.queryTime);

  // 2. Language switching: tc should return Traditional Chinese text.
  const tc = await getEta2('1', '946C74E30100FE80', 'tc');
  check('tc name is Traditional Chinese-ish', /[一-鿿]/.test(resolveText(tc.etas[0].dest, 'tc')), resolveText(tc.etas[0].dest, 'tc'));

  // 3. Error path: unknown stop -> 404 ApiError.
  let threw = null;
  try { await getEta2('1', 'DEADBEEF', 'en'); } catch (e) { threw = e; }
  check('404 -> ApiError with code RESOURCE_NOT_FOUND', threw instanceof ApiError && threw.status === 404 && threw.code === 'RESOURCE_NOT_FOUND', threw && { status: threw.status, code: threw.code });

  // 4. checkRouteStop: 404 -> false, 200 -> true.
  const bad = await checkRouteStop('1', 'DEADBEEF', 'en');
  check('checkRouteStop false on 404', bad === false);
  const good = await checkRouteStop('1', '946C74E30100FE80', 'en');
  check('checkRouteStop true on 200', good === true);

  // 5. Network-down path: unreachable host -> NETWORK_ERROR.
  process.env.EXPO_PUBLIC_API_BASE = 'http://127.0.0.1:9/';
  delete require.cache[require.resolve(path.join(compiled, 'api.js'))];
  const { getEta: getEta3 } = require(path.join(compiled, 'api.js'));
  let netErr = null;
  try { await getEta3('1', '946C74E30100FE80', 'en'); } catch (e) { netErr = e; }
  check('unreachable -> ApiError NETWORK_ERROR', netErr instanceof ApiError && netErr.code === 'NETWORK_ERROR', netErr && netErr.code);

  console.log(failures === 0 ? '\nALL PASSED' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
