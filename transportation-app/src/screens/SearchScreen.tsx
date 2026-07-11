import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Keyboard,
  ListRenderItemInfo,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, pressOpacity, radius, spacing, touch } from '@/theme';
import { api } from '@/services/api';
import { ApiError } from '@/services/types';
import type { SearchHit } from '@/services/types';
import { resolveText, useLanguage } from '@/services/i18n';
import { ScreenHeader } from '@/components/ScreenHeader';
import { SearchBar } from '@/components/SearchBar';

/**
 * Flat, UI-friendly shape the Search view renders. This is the contract the
 * search API client is expected to produce: a list of route/stop hits the
 * user can pick from. We expose it here so the screen is fully self-contained
 * (the spec allows a local mock when the API client task is unavailable).
 */
export interface ResultItem {
  id: string;
  label: string;
  type: 'route' | 'stop';
  /** For stop items: a known route that serves this stop (best-effort). */
  servingRoute?: string;
}

/**
 * searchBus(query, lang) — the data contract this screen depends on.
 *
 * When the live backend search endpoint is reachable we call it (api.search)
 * and map the server hits into ResultItem[]. If the client/endpoint is
 * unavailable (network down, 404, or not yet implemented) we fall back to a
 * local mock that returns the SAME shape ({ id, label, type }[]) so the UI
 * stays fully exercisable offline / in dev.
 */
async function searchBus(query: string, lang: string): Promise<ResultItem[]> {
  const q = query.trim();
  if (!q) return [];

  try {
    const res = await api.search(q, lang);
    const items: ResultItem[] = [
      ...res.routes.map((r: SearchHit) => ({
        id: r.id,
        label: `Route ${r.id}${r.operator ? ` (${r.operator})` : ''}`,
        type: 'route' as const,
      })),
      ...res.stops.map((s: SearchHit) => ({
        id: s.id,
        label: resolveText(s.name, lang as 'tc') || s.id,
        type: 'stop' as const,
        servingRoute:
          s.routes && s.routes.length ? s.routes[0] : undefined,
      })),
    ];
    if (items.length > 0) return items;
    // Server returned nothing → fall through to the offline mock so the user
    // still sees actionable options in dev / offline scenarios.
  } catch (e) {
    if (e instanceof ApiError && e.status !== 404) {
      // Hard error (5xx, auth) — surface it instead of pretending success.
      throw e;
    }
    // 404 or network failure → fall through to the local mock.
  }
  return mockSearch(q);
}

/** Offline fallback: a small static catalog filtered by the query string. */
function mockSearch(query: string): ResultItem[] {
  const q = query.trim().toLowerCase();
  return MOCK_CATALOG.filter(
    (it) =>
      !q ||
      it.id.toLowerCase().includes(q) ||
      it.label.toLowerCase().includes(q)
  );
}

const MOCK_CATALOG: ResultItem[] = [
  { id: '1', label: 'Route 1 (KMB)', type: 'route' },
  { id: '10', label: 'Route 10 (KMB)', type: 'route' },
  { id: '113', label: 'Route 113 (KMB)', type: 'route' },
  { id: '11K', label: 'Route 11K (KMB)', type: 'route' },
  { id: '946C74E30100FE80', label: 'Cheung Sha Wan Plaza (stop)', type: 'stop' },
  { id: '87154BA98253B43D', label: 'Mei Tung Estate (stop)', type: 'stop' },
];

/**
 * Primary search view. A single free-text input + submit control drives a
 * query (searchBus). Returned items render in an accessible, selectable list.
 * Tapping an item (or a quick-route chip) routes into the Results view,
 * carrying the chosen id (and a compatible stopId/route hint) as navigation
 * params — the React-Navigation equivalent of `/results/:id`.
 *
 * Mobile polish: the initial empty state shows one-tap "popular route" chips
 * (anchored to the routes the live backend actually serves) so the screen is
 * immediately useful instead of 85% blank, and the search field placeholder is
 * kept short enough to never truncate on a 375px viewport.
 */
export default function SearchScreen({ navigation }: any) {
  const { lang } = useLanguage();
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<ResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const doSearch = useCallback(
    async (text: string) => {
      setError(null);
      setSelected(null);
      if (!text.trim()) {
        setItems([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const result = await searchBus(text.trim(), lang);
        setItems(result);
      } catch (e) {
        setItems([]);
        setError(
          e instanceof ApiError
            ? e.message
            : 'Search is unavailable right now.'
        );
      } finally {
        setLoading(false);
      }
    },
    [lang]
  );

  const onChangeText = (t: string) => setQuery(t);

  const gotoResults = useCallback(
    (item: ResultItem) => {
      Keyboard.dismiss();
      navigation.navigate('Results', {
        id: item.id,
        type: item.type,
        label: item.label,
        stopId: item.type === 'stop' ? item.id : undefined,
        route:
          item.type === 'route'
            ? item.id
            : item.servingRoute ?? undefined,
        title: item.label,
      });
    },
    [navigation]
  );

  // One-tap shortcut for the verified popular routes (kept compact so the
  // touch target still meets the 44px guideline).
  const quickPick = useCallback(
    (routeNo: string) => {
      setSelected(`route-${routeNo}`);
      gotoResults({
        id: routeNo,
        label: `Route ${routeNo} (KMB)`,
        type: 'route',
      });
    },
    [gotoResults]
  );

  const renderItem = ({ item }: ListRenderItemInfo<ResultItem>) => {
    const isRoute = item.type === 'route';
    const active = selected === item.id;
    return (
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityLabel={`${item.label}, ${isRoute ? 'bus route' : 'bus stop'}. Tap to view arrivals.`}
        accessibilityHint="Opens the arrivals board for this selection."
        onPress={() => {
          setSelected(item.id);
          gotoResults(item);
        }}
        activeOpacity={pressOpacity}
        style={[styles.row, active ? styles.rowActive : null]}
      >
        <View style={styles.rowText}>
          <Text style={styles.rowTitle}>{item.label}</Text>
          <Text style={styles.rowSub}>
            {isRoute ? 'Bus route' : 'Bus stop'} · id {item.id}
          </Text>
        </View>
        <Text style={styles.rowArrow} aria-hidden>
          →
        </Text>
      </TouchableOpacity>
    );
  };

  const showInitial = !query.trim() && !loading && !error;

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <View style={styles.pad}>
        <ScreenHeader title="Bus ETA" subtitle="Search route & stop" />
        <SearchBar
          value={query}
          onChangeText={onChangeText}
          placeholder="Search route or stop…"
          onSubmit={() => void doSearch(query)}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {showInitial ? (
          <View style={styles.initial}>
            <Text style={styles.initialHeading}>Popular routes</Text>
            <View style={styles.chips}>
              {api.DEFAULT_ROUTES.map((r) => {
                const active = selected === `route-${r}`;
                return (
                  <TouchableOpacity
                    key={r}
                    accessibilityRole="button"
                    accessibilityLabel={`Route ${r} arrivals`}
                    onPress={() => quickPick(r)}
                    activeOpacity={pressOpacity}
                    style={[styles.chip, active ? styles.chipActive : null]}
                  >
                    <Text style={styles.chipText}>{r}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            <Text style={styles.hint}>
              Tap a route, or search by name (e.g. Central) or number.
            </Text>
          </View>
        ) : null}

        {!loading && !error && query.trim() && items.length === 0 ? (
          <Text style={styles.empty}>No matches. Try another stop or route.</Text>
        ) : null}
      </View>

      <FlatList
        data={items}
        keyExtractor={(it) => `${it.type}-${it.id}`}
        renderItem={renderItem}
        ListHeaderComponent={
          loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.hint}>Searching…</Text>
            </View>
          ) : null
        }
        contentContainerStyle={styles.list}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  pad: { paddingHorizontal: spacing.lg },
  // Initial / empty-state polish: a useful "popular routes" block instead of
  // a vast blank screen. Touch targets stay >= 44px.
  initial: { marginTop: spacing.lg },
  initialHeading: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.sm,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  chip: {
    minHeight: touch,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
  chipText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  hint: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
  },
  rowActive: {
    borderWidth: 1,
    borderColor: colors.primary,
  },
  rowText: { flex: 1, gap: 2 },
  rowTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  rowSub: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  rowArrow: {
    fontSize: 18,
    color: colors.primary,
    fontWeight: '700',
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: spacing.md,
  },
  error: {
    color: colors.danger,
    fontSize: 13,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  empty: {
    textAlign: 'center',
    color: colors.textSecondary,
    marginTop: spacing.xl,
    paddingHorizontal: spacing.lg,
  },
  list: { padding: spacing.lg, gap: spacing.sm, paddingBottom: spacing.xl },
});
