import { EtaAggregate, SearchResponse } from './types';

/**
 * Mock data layer. Returns realistic data shapes that match the live
 * GET /api/v1/eta and GET /api/v1/search payloads, so the UI renders
 * meaningfully when the backend is down — or when VITE_USE_MOCK=true.
 */

export const MOCK_API_BASE = '__mock__';

const ROUTE_TERMINALS: Record<string, { en: string; tc: string; sc: string }> = {
  '1': { en: 'Star Ferry', tc: '尖沙咀碼頭', sc: '尖沙咀码头' },
  '10': { en: 'Kennedy Town', tc: '堅尼地城', sc: '坚尼地城' },
  '113': { en: 'Cross Harbour Tunnel', tc: '紅磡海底隧道', sc: '红磡海底隧道' },
  '11K': { en: 'Hung Hom Station', tc: '紅磡車站', sc: '红磡车站' },
};

const REMARKS: Record<string, { en: string; tc: string; sc: string }> = {
  on_time: { en: 'On time', tc: '準時', sc: '准时' },
  delayed: { en: 'Delayed', tc: '延誤', sc: '延误' },
  departed: {
    en: 'The final bus has departed from this stop',
    tc: '最後班次已過',
    sc: '最后班次已过',
  },
};

export function getMockEta(
  route: string,
  stop: string,
  lang: string
): EtaAggregate {
  const terminal =
    ROUTE_TERMINALS[route] || { en: 'Terminus', tc: '總站', sc: '总站' };
  const now = new Date();
  const mkEta = (mins: number | null, seq: number, remarkKey?: string) => {
    const etaTime = mins === null ? null : new Date(now.getTime() + mins * 60000);
    return {
      co: 'KMB',
      route,
      direction: 'O' as const,
      serviceType: 1,
      seq,
      dest: terminal,
      etaSeq: seq,
      eta: etaTime ? etaTime.toISOString() : '',
      minutesRemaining: mins,
      remark: remarkKey ? REMARKS[remarkKey] : null,
      dataTimestamp: now.toISOString(),
      status: mins === null ? ('scheduled' as const) : ('live' as const),
    };
  };

  const etas =
    route === '1'
      ? [mkEta(3, 1), mkEta(12, 2), mkEta(25, 3), mkEta(null, 4, 'departed')]
      : [mkEta(7, 1), mkEta(19, 2)];

  return {
    query: { route, stopId: stop, operator: 'KMB', lang },
    etas,
    weather: {
      temperature: { place: '香港天文台', value: 30, unit: 'C' },
      description: '天色良好',
      humidity: { value: 83, unit: 'percent' },
      icon: [75],
      updateTime: now.toISOString(),
      warnings: [
        {
          code: 'WTHU',
          title: {
            en: 'Thunderstorm Warning',
            tc: '雷暴警告',
            sc: '雷暴警告',
          },
          severity: 'red',
          contents: '雷暴警告現正生效，香港地區有幾陣狂風雷暴。',
          issueTime: now.toISOString(),
        },
        {
          code: 'WHOT',
          title: {
            en: 'Very Hot Weather Warning',
            tc: '酷熱天氣警告',
            sc: '酷热天气警告',
          },
          severity: 'warning',
          contents: '酷熱天氣警告現正生效。',
          issueTime: now.toISOString(),
        },
      ],
      forecast: null,
    },
    incidents: [
      {
        id: 'IN-MOCK-001',
        heading: { en: 'Road Incident', tc: '道路事故', sc: '道路事故' },
        detail: { en: 'Traffic Accident', tc: '交通意外', sc: '交通意外' },
        location: { en: 'Kwun Tong Road', tc: '觀塘道', sc: '觀塘道' },
        district: null,
        status: { en: 'NEW', tc: '最新情況', sc: '最新情况' },
        relevance: 'high',
        announcementDate: now.toISOString().slice(0, 16).replace('T', ' '),
        content: {
          en: 'Part of Kwun Tong Road closed due to traffic accident.',
          tc: '觀塘道因交通意外部分行車線封閉。',
          sc: '觀塘道因交通意外部分行车线封闭。',
        },
      },
    ],
    queryTime: now.toISOString(),
    degraded: false,
    mock: true,
  };
}

const MOCK_STOPS: Record<string, { en: string; tc: string; sc: string }> = {
  '946C74E30100FE80': { en: 'Cheung Sha Wan Plaza', tc: '長沙灣廣場', sc: '长沙湾广场' },
  'ABC1230000000001': { en: 'Central Station', tc: '中環站', sc: '中环站' },
  'ABC1230000000002': { en: 'Admiralty Station', tc: '金鐘站', sc: '金钟站' },
};

export function getMockSearch(q: string, lang: string): SearchResponse {
  const needle = q.trim().toLowerCase();
  if (!needle) {
    return { query: q, lang, total: 0, stops: [], routes: [] };
  }

  const routes = Object.keys(ROUTE_TERMINALS)
    .filter((r) => r.toLowerCase().includes(needle))
    .map((r) => ({
      id: r,
      kind: 'route' as const,
      operator: 'KMB',
      name: ROUTE_TERMINALS[r],
    }));

  const stops = Object.entries(MOCK_STOPS)
    .filter(([, n]) =>
      [n.en, n.tc, n.sc].some((t) => t.toLowerCase().includes(needle))
    )
    .map(([id, n]) => ({
      id,
      kind: 'stop' as const,
      name: n,
      routes: routes.map((r) => r.id),
    }));

  return {
    query: q,
    lang,
    total: routes.length + stops.length,
    stops,
    routes,
  };
}
