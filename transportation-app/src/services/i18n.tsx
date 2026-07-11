/**
 * Lightweight i18n for the Bus ETA app.
 *
 * The backend returns all text as multilingual objects `{ en, tc, sc }` and
 * the client asks for a single `lang`. `resolveText` collapses a
 * MultilingualText into the best available string for the active language,
 * falling back tc -> en -> sc so the UI never shows an empty value.
 *
 * `etaLiveStatus` derives the live/scheduled display status from the remark
 * text (the backend does not carry an explicit flag).
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';
import type { ETA, Lang, MultilingualText } from './types';

const LANGS: Lang[] = ['en', 'tc', 'sc'];

const LanguageContext = createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
  cycleLang: () => void;
}>({
  lang: 'tc',
  setLang: () => {},
  cycleLang: () => {},
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>('tc');

  const setLang = useCallback((l: Lang) => setLangState(l), []);
  const cycleLang = useCallback(() => {
    setLangState((prev) => {
      const i = LANGS.indexOf(prev);
      return LANGS[(i + 1) % LANGS.length];
    });
  }, []);

  const value = useMemo(
    () => ({ lang, setLang, cycleLang }),
    [lang, setLang, cycleLang]
  );

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}

/** Resolve a multilingual text field to the best string for the language. */
export function resolveText(
  field: MultilingualText | string | null | undefined,
  lang: Lang = 'tc'
): string {
  if (!field) return '';
  // Already resolved scalar (e.g. weather.description) — pass through.
  if (typeof field === 'string') return field;
  return field[lang] || field.tc || field.en || field.sc || '';
}

const LIVE_RE = /(live|real|gps|正在|實時|实時|即時)/i;

/** Derive 'live' vs 'scheduled' from the (resolved) remark text. */
export function etaLiveStatus(
  remark: string | null | undefined
): ETA['status'] {
  return remark && LIVE_RE.test(remark) ? 'live' : 'scheduled';
}
