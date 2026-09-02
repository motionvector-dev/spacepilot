import { useCallback, useEffect, useState } from 'react';

export type ThemePreference = 'system' | 'light' | 'dark';

// Same key the vanilla studio pages use, so a choice made on one surface is
// still there on the other.
const KEY = 'pluto-theme';

function isPreference(v: string | null): v is ThemePreference {
  return v === 'light' || v === 'dark' || v === 'system';
}

/** ?theme=light|dark|system wins over storage for this load.
 *
 * It is how a screenshot, a doc link, or a bug report pins the theme without
 * touching the reader's own choice. index.html reads the same parameter before
 * first paint. Anything else in the parameter is ignored, not guessed at. */
function readPreference(): ThemePreference {
  try {
    const q = new URLSearchParams(window.location.search).get('theme');
    if (isPreference(q)) return q;
  } catch {
    /* a malformed query string is not worth failing over */
  }
  try {
    const v = localStorage.getItem(KEY);
    if (isPreference(v)) return v;
  } catch {
    /* private mode, or storage disabled */
  }
  return 'system';
}

/** The query asks for LIGHT rather than dark on purpose: a browser that
 *  reports no preference at all lands on dark, matching the bare :root
 *  fallback in tokens.css. ui/index.html runs the same test before first
 *  paint — keep the two in step. */
function systemIsDark(): boolean {
  return !window.matchMedia('(prefers-color-scheme: light)').matches;
}

/** Store the preference; apply the resolved value.
 *
 * System is the default (Saurabh, 2026-09-02, PR 107): while the preference
 * is "system", no data-theme attribute is stamped at all, and tokens.css's
 * guarded `@media (prefers-color-scheme: light)` block decides the palette —
 * the same mechanism the OS itself uses to notify a change, so no listener
 * even has to redraw. The attribute is stamped only once the user picks
 * Light or Dark explicitly, which is also what makes that choice win over a
 * later OS change.
 */
function apply(pref: ThemePreference) {
  if (pref === 'system') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', pref);
  }
  // The vanilla stylesheets key off body classes; keep them in step so the two
  // surfaces do not disagree if someone navigates between them.
  const resolved = pref === 'system' ? (systemIsDark() ? 'dark' : 'light') : pref;
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
    const mq = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = () => apply('system');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [preference]);

  const resolved: 'light' | 'dark' =
    preference === 'system' ? (systemIsDark() ? 'dark' : 'light') : preference;

  return { preference, resolved, setPreference: useCallback(setPreference, []) };
}
