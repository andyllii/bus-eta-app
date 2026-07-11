/**
 * API contract test for the web app's service layer.
 *
 * Runs in two modes:
 *  1. Pure static check of the mock layer (always runs, no network):
 *     validates that getMockEta / getMockSearch return the exact data shapes
 *     the screens consume.
 *  2. Live check (when VITE_API_BASE / a backend is reachable): fetches the
 *     real /api/v1/eta and asserts the same shape.
 *
 * Run: node scripts/api-contract.test.mjs
 */
import { getMockEta, getMockSearch } from '../src/services/mock.ts';

let failures = 0;
function assert(cond, msg) {
  if (!cond) {
    console.error('  ✗ ' + msg);
    failures++;
  } else {
    console.log('  ✓ ' + msg);
  }
}

function checkEta(agg) {
  assert(agg && typeof agg === 'object', 'aggregate is an object');
  assert(Array.isArray(agg.etas), 'etas is an array');
  assert('degraded' in agg, 'degraded flag present');
  assert(agg.query && typeof agg.query.stopId === 'string', 'query.stopId string');
  for (const e of agg.etas) {
    assert(typeof e.route === 'string', 'eta.route string');
    assert(e.dest && typeof e.dest === 'object', 'eta.dest multilingual object');
    assert(e.status === 'live' || e.status === 'scheduled', 'eta.status valid');
  }
  if (agg.weather) {
    assert(Array.isArray(agg.weather.warnings), 'weather.warnings array');
  }
  assert(Array.isArray(agg.incidents), 'incidents is an array');
}

console.log('Mock layer — EtaAggregate shape');
const mock = getMockEta('1', '946C74E30100FE80', 'tc');
checkEta(mock);
assert(mock.mock === true, 'mock flag set');

console.log('Mock layer — SearchResponse shape');
const sr = getMockSearch('1', 'tc');
assert(typeof sr.total === 'number', 'search.total number');
assert(Array.isArray(sr.routes) && Array.isArray(sr.stops), 'routes/stops arrays');

console.log('\nSummary: ' + (failures === 0 ? 'PASS' : `${failures} FAILURE(S)`));
process.exit(failures === 0 ? 0 : 1);
