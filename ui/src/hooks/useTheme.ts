import { useCallback, useEffect, useState } from 'react';

export type ThemePreference = 'system' | 'light' | 'dark';

// Same key the vanilla studio pages use, so a choice made on one surface is
// still there on the other.
const KEY = 'pluto-theme';

function readPreference(): ThemePreference {
  try {
    const v = localStorage.getItem(KEY);
    if (v === 'light' || v === 'dark' || v === 'system') return v;
  } catch {
    /* private mode, or storage disabled */
  }
  return 'system';
}

function systemIsDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/** Store the preference; apply the resolved value.
 *
 * These have to be separate. Tailwind's dark variant matches [data-theme="dark"]
 * exactly, so writing data-theme="system" — which is what the vanilla theme.js
 * does — leaves every dark: utility inert while the OS is in dark mode. The
 * attribute therefore always says light or dark, and "system" lives in storage.
 */
function apply(pref: ThemePreference) {
  const resolved = pref === 'system' ? (systemIsDark() ? 'dark' : 'light') : pref;
  document.documentElement.setAttribute('data-theme', resolved);
  // The vanilla stylesheets key off body classes; keep them in step so the two
  // surfaces do not disagree if someone navigates between them.
  document.body?.classList.toggle('light-theme', resolved === 'light');
  document.body?.classList.toggle('dark-theme', resolved === 'dark');
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(readPreference);

  useEffect(() => {
    apply(preference);
    try {
      localStorage.setItem(KEY, preference);
    } catch {
      /* preference simply will not persist */
    }
  }, [preference]);

  // Follow the OS while the preference is "system", including a change made
  // after the page loaded.
  useEffect(() => {
    if (preference !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => apply('system');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [preference]);

  const resolved: 'light' | 'dark' =
    preference === 'system' ? (systemIsDark() ? 'dark' : 'light') : preference;

  return { preference, resolved, setPreference: useCallback(setPreference, []) };
}
