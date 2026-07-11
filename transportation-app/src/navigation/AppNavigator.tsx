import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { colors } from '@/theme';
import SearchScreen from '@/screens/SearchScreen';
import ResultsScreen from '@/screens/ResultsScreen';

const Stack = createNativeStackNavigator();

/**
 * Root navigator. A native stack hosts the Search (primary, route+stop picker)
 * screen and the combined Results ("next bus" board) screen. Results consumes
 * the PRIMARY endpoint GET /api/v1/eta and shows ETAs + weather + traffic in
 * one mobile-first view.
 *
 * (The earlier bottom-tab layout — Search / Arrivals / Info — is consolidated
 * into a single combined Results screen, since the task requires one clear,
 * combined view rather than three screens duplicating the same data.)
 */
export default function AppNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen
        name="Search"
        component={SearchScreen}
        options={{ title: 'Bus ETA' }}
      />
      <Stack.Screen
        name="Results"
        component={ResultsScreen}
        options={{ title: 'Arrivals' }}
      />
    </Stack.Navigator>
  );
}
