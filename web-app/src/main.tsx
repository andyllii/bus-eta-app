import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { LanguageProvider } from './lang-context';
import { TopBar } from './components/TopBar';
import { SearchScreen } from './screens/SearchScreen';
import './index.css';

// Code-split the results view: it pulls in the ETA/weather/traffic rendering
// and the icon set, which only matters after the user picks a route/stop. The
// landing SearchScreen stays in the initial bundle so first paint is tiny.
const ResultsScreen = lazy(() =>
  import('./screens/ResultsScreen').then((m) => ({ default: m.ResultsScreen }))
);

// Sized fallback that mirrors the real ResultsScreen's *loading* state (back
// link + reserved mock-banner slot + reserved 60vh content) so every
// transition — fallback → real skeleton → loaded data — shifts nothing
// (CLS = 0). The mock banner only appears once data arrives, and the real
// screen reserves the same height from first paint, so its reveal is seamless.
function ResultsFallback() {
  return (
    <div className="mx-auto max-w-app px-4 py-4">
      <div className="mb-3 h-11" />
      <div className="mb-3 flex h-[34px] items-center rounded-lg px-3" />
      <div className="min-h-[60dvh]">
        <p className="mt-10 text-center text-sm text-gray-400">
          載入中 · Loading…
        </p>
      </div>
    </div>
  );
}

function App() {
  return (
    <LanguageProvider>
      <div className="min-h-screen w-full bg-gray-50 text-gray-900">
        <TopBar title="巴士到站 · Bus ETA" />
        <main className="mx-auto w-full max-w-app pb-10">
          <Routes>
            <Route path="/" element={<SearchScreen />} />
            <Route
              path="/results"
              element={
                <Suspense fallback={<ResultsFallback />}>
                  <ResultsScreen />
                </Suspense>
              }
            />
            <Route path="*" element={<SearchScreen />} />
          </Routes>
        </main>
      </div>
    </LanguageProvider>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
