import { Lang, MultilingualText } from './services/types';

/** Resolve a multilingual field to the active language, with graceful fallback. */
export function resolveText(
  text: MultilingualText | string | null | undefined,
  lang: Lang
): string {
  if (!text) return '';
  if (typeof text === 'string') return text;
  return (
    text[lang] ||
    text.tc ||
    text.en ||
    text.sc ||
    ''
  );
}

const LANG_LABELS: Record<Lang, string> = {
  en: 'EN',
  tc: '繁',
  sc: '简',
};

export function langLabel(lang: Lang): string {
  return LANG_LABELS[lang];
}
