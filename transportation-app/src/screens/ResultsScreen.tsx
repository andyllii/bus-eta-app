import React, { useMemo, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, spacing } from '@/theme';
import { useEtaData } from '@/services/useEtaData';
import { useLanguage } from '@/services/i18n';
import { api } from '@/services/api';
import type { ETA, Incident } from '@/services/types';
import {
  ErrorState,
  formatClock,
  LoadingState,
  ScreenHeader,
} from '@/components/ScreenHeader';
import { EtaCard } from '@/components/EtaCard';
import { WeatherStrip } from '@/components/WeatherWidget';
import { TrafficAlertBanner } from '@/components/TrafficAlertBanner';
import { LangToggle } from '@/components/LangToggle';
import { BackButton } from '@/components/BackButton';
import { SoftErrorBanner } from '@/components/SoftErrorBanner';
import { DegradedBanner } from '@/components/DegradedBanner';
import { FadeIn } from '@/components/FadeIn';

/**
 * Results view (the combined "next bus" board). Consumes the PRIMARY endpoint
 * GET /api/v1/eta?route=&stop= and presents, in one scrollable mobile screen:
 *
 *   1. Header: route + stop name, "updated HH:MM", live weather widget.
 *   2. Weather strip: current conditions + active warnings (thunderstorm icon).
 *   3. Dismissible traffic-alert banners for incidents affecting THIS route,
 *      ranked high-first by the server-computed relevance.
 *   4. The list of upcoming ETAs for the route at the stop.
 *
 * It refreshes periodically (30s) and supports pull-to-refresh. A soft-error
 * banner appears if a background refresh fails but we still have data; a
 * degraded banner appears when the server skipped a partial provider.
 */
export default function ResultsScreen({ route, navigation }: any) {
  const { id, type, route: routeNo, stopId, title } = route.params ?? {};
  const { lang } = useLanguage();
  // The Search screen selects an item and passes the chosen id (and a
  // compatible route/stop hint). A route selection lands on its verified
  // default stop; a stop selection carries a serving route so the board is
  // populated. Built-in fallbacks keep the screen usable standalone.
  const r = routeNo ?? (type === 'stop' ? '1' : '1');
  const id2 = stopId ?? (type === 'route' ? '946C74E30100FE80' : id ?? '946C74E30100FE80');

  const [dismissed, setDismissed] = useState<Record<string, boolean>>({});

  const {
    data,
    loading,
    refreshing,
    error,
    softError,
    degraded,
    lastUpdated,
    refresh,
  } = useEtaData(r, id2, lang);

  const etas: ETA[] = data?.etas ?? [];
  // The API does not return a stop name. Prefer the friendly title passed from
  // the Search screen; otherwise localise the stop id from the built-in catalog
  // in the active language; fall back to the raw id only as a last resort.
  const stopName = title || api.localizeStopName(null, id2, lang);
  const incidents: Incident[] = useMemo(
    () => (data?.incidents ?? []).filter((i) => !dismissed[i.id]),
    [data?.incidents, dismissed]
  );
  const subtitle = lastUpdated ? `Updated ${formatClock(lastUpdated)}` : undefined;

  if (loading) return <LoadingState label="Loading arrivals…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      {softError ? (
        <SoftErrorBanner message={softError} onRetry={refresh} />
      ) : null}
      {degraded ? <DegradedBanner /> : null}

      {/* Header: route + stop title/subtitle on its own line, with the
          weather widget and language toggle laid out below so nothing is
          squeezed on a 375px screen. On wider viewports it still reads fine. */}
      <View style={styles.pad}>
        <ScreenHeader
          title={`Route ${r} · ${stopName}`}
          subtitle={subtitle}
          titleNumberOfLines={2}
        />
        {/* Header controls: back button + language toggle on one row so the
            row never wraps awkwardly at 375px. The weather widget drops to its
            own full-width line below (see WeatherStrip for the full detail). */}
        <View style={styles.headerRow}>
          <BackButton
            onPress={() => {
              if (navigation?.canGoBack?.()) navigation.goBack();
              else navigation?.navigate?.('Search');
            }}
          />
          <LangToggle />
        </View>
      </View>

      <FlatList
        data={etas}
        keyExtractor={(e, i) => `${e.route}-${e.etaSeq}-${i}`}
        renderItem={({ item }) => (
          <FadeIn delay={Math.min(etas.indexOf(item) * 40, 240)}>
            <EtaCard eta={item} lang={lang} />
          </FadeIn>
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} />
        }
        ListHeaderComponent={
          <View style={styles.contextCol}>
            <WeatherStrip weather={data?.weather} lang={lang} />
            {incidents.length > 0 ? (
              <View style={styles.banners}>
                <Text style={styles.bannerHeading}>Traffic alerts on this route</Text>
                {incidents.map((inc) => (
                  <TrafficAlertBanner
                    key={inc.id}
                    incident={inc}
                    lang={lang}
                    onDismiss={() =>
                      setDismissed((d) => ({ ...d, [inc.id]: true }))
                    }
                  />
                ))}
              </View>
            ) : null}
          </View>
        }
        ListEmptyComponent={<ErrorState message="No upcoming arrivals." />}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  pad: { paddingHorizontal: spacing.lg },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  contextCol: { gap: spacing.md, paddingBottom: spacing.sm },
  banners: { gap: spacing.sm },
  bannerHeading: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  list: { padding: spacing.lg, gap: spacing.md },
});
