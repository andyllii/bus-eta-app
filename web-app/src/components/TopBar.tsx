import { useLanguage } from '../lang-context';
import { langLabel } from '../i18n';

/**
 * Fixed top app bar with a title and a compact language switcher (EN / 繁 / 简).
 * Mobile-first: hugs the top, never scrolls away.
 */
export function TopBar({ title }: { title: string }) {
  const { lang, setLang } = useLanguage();
  const langs: ('en' | 'tc' | 'sc')[] = ['en', 'tc', 'sc'];
  return (
    <header className="sticky top-0 z-10 bg-brand text-white shadow">
      <div className="mx-auto flex max-w-app items-center justify-between px-4 py-3">
        <h1 className="text-base font-semibold tracking-wide">{title}</h1>
        <div className="flex gap-1">
          {langs.map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              aria-pressed={lang === l}
              className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded px-2 text-xs font-medium transition ${
                lang === l
                  ? 'bg-white text-brand'
                  : 'bg-brand-dark/60 text-white/80 hover:bg-brand-dark'
              }`}
            >
              {langLabel(l)}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
