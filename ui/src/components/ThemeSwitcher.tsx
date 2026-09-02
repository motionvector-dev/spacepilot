import { useTheme, type ThemePreference } from '../hooks/useTheme';

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

/** Three states, not a toggle. "System" is a real choice — it means follow the
 *  machine — and collapsing it into a two-way switch loses that. */
export function ThemeSwitcher() {
  const { preference, setPreference } = useTheme();

  return (
    <div
      role="group"
      aria-label="Colour theme"
      className="fixed bottom-4 right-4 z-[100] flex gap-[3px] p-[3px] rounded-md
                 bg-surface border border-line-200"
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={preference === o.value}
          onClick={() => setPreference(o.value)}
          className={`h-6 px-3 rounded text-[11px] font-mono cursor-pointer
            transition-[background-color,color] duration-[120ms]
            ${preference === o.value
              ? 'bg-accent text-accent-contrast'
              : 'text-ink-500 hover:text-ink hover:bg-raised-hover'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
