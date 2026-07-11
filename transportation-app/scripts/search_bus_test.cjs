/**
 * Standalone functional test for the UI-free `searchBus` module.
 *
 * Spins up a REAL local HTTP server that mimics the backend
 * `GET /api/v1/search` endpoint (snake_case wire shape), then exercises the
 * compiled `searchBus` client against it and asserts the acceptance contract:
 *
 *   1. A route query maps to `{ id, label, type:'route' }` with a
 *      "<route> · <outbound terminal>" label.
 *   2. A stop query maps to `{ id, label, type:'stop' }` with the resolved
 *      stop name as the label.
 *   3. An empty query resolves to `[]` (no round-trip / empty list).
 *   4. A no-match query resolves to `[]` (HTTP 200, zero hits).
 *   5. A 500 response rejects with `ApiError` (status 500, code INTERNAL_ERROR).
 *   6. A dropped connection rejects with `ApiError` (status 0, NETWORK_ERROR).
 *
 * Run (compiles TS to .out-test first): node scripts/search_bus_test.cjs
 * Via npm: npm run test:search
 */
const http = require('http');
const path = require('path');

const appDir = path.resolve(__dirname, '..');
const compiled = path.join(appDir, '.out-test');

// A faithful snapshot of the backend's snake_case payload for a "1" route query.
function buildRoutePayload(q) {
  return {
    query: q,
    lang: 'tc',
    total: 1,
    stops: [],
    routes: [
      {
        id: '1',
        operator: 'KMB',
        kind: 'route',
        name: null,
        destinations: {
          O: { en: 'Central (Macao Ferry)' },
          I: { en: 'Cheung Sha Wan Plaza' },
        },
      },
    ],
  };
}

function buildStopPayload(q) {
  return {
    query: q,
    lang: 'tc',
    total: 1,
    stops: [
      {
        id: '946C74E30100FE80',
        operator: 'KMB',
        kind: 'stop',
        name: { en: 'Cheung Sha Wan Plaza' },
        address: { en: 'Cheung Sha Wan Road, Kowloon' },
        location: { lat: 22.333, lon: 114.161 },
        routes: ['1', '10', '113', '11K'],
      },
    ],
    routes: [],
  };
}

function buildEmptyPayload(q) {
  return { query: q, lang: 'tc', total: 0, stops: [], routes: [] };
}

const server = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://localhost');
  if (u.pathname !== '/api/v1/search') {
    res.writeHead(404);
    res.end();
    return;
  }
  const q = u.searchParams.get('q') || '';

  if (q === 'boom') {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ code: 'INTERNAL_ERROR', message: 'Search failed.' }));
    return;
  }
  if (q === 'net') {
    // Abruptly tear down the socket so fetch() raises a network error.
    res.destroy();
    return;
  }
  if (q.toLowerCase().includes('cheung')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(buildStopPayload(q)));
    return;
  }
  if (q === '1') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(buildRoutePayload(q)));
    return;
  }
  // Anything else (incl. empty) → zero hits.
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(buildEmptyPayload(q)));
});

let failures = 0;
function check(name, cond, extra) {
  if (cond) {
    console.log('  ok  -', name);
  } else {
    console.error('  FAIL-', name, extra != null ? JSON.stringify(extra) : '');
    failures++;
  }
}

(async () => {
  // Point the client at our mock server. The client reads API_BASE at import
  // time, so set the env var BEFORE requiring the compiled module.
  process.env.EXPO_PUBLIC_API_BASE = 'http://127.0.0.1:0';
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  process.env.EXPO_PUBLIC_API_BASE = `http://127.0.0.1:${port}`;

  const { searchBus } = require(path.join(compiled, 'searchBus.js'));
  const { ApiError } = require(path.join(compiled, 'types.js'));

  try {
    // 1. Route query → single route result with terminal label.
    const routeHits = await searchBus('1');
    check('route query returns 1 result', routeHits.length === 1);
    check(
      'route result shape + label',
      routeHits[0] &&
        routeHits[0].id === '1' &&
        routeHits[0].type === 'route' &&
        routeHits[0].label === '1 · Central (Macao Ferry)',
      routeHits[0]
    );

    // 2. Stop query → single stop result with resolved name.
    const stopHits = await searchBus('cheung');
    check('stop query returns 1 result', stopHits.length === 1);
    check(
      'stop result shape + label',
      stopHits[0] &&
        stopHits[0].id === '946C74E30100FE80' &&
        stopHits[0].type === 'stop' &&
        stopHits[0].label === 'Cheung Sha Wan Plaza',
      stopHits[0]
    );

    // 3. Empty query → [].
    const empty = await searchBus('   ');
    check('empty query resolves to []', Array.isArray(empty) && empty.length === 0);

    // 4. No-match query (HTTP 200, zero hits) → [].
    const none = await searchBus('zzzznomatch');
    check('no-match query resolves to []', Array.isArray(none) && none.length === 0);

    // 5. 500 → rejects with ApiError(status 500).
    let boomErr = null;
    try {
      await searchBus('boom');
    } catch (e) {
      boomErr = e;
    }
    check(
      '500 rejects ApiError with code',
      boomErr instanceof ApiError &&
        boomErr.status === 500 &&
        boomErr.code === 'INTERNAL_ERROR'
    );

    // 6. Dropped connection → rejects with ApiError(status 0, NETWORK_ERROR).
    let netErr = null;
    try {
      await searchBus('net');
    } catch (e) {
      netErr = e;
    }
    check(
      'network failure rejects ApiError(0, NETWORK_ERROR)',
      netErr instanceof ApiError &&
        netErr.status === 0 &&
        netErr.code === 'NETWORK_ERROR'
    );
  } finally {
    server.close();
  }

  console.log(failures === 0 ? '\nALL PASSED' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
