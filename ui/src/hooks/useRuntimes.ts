import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface RuntimeStatus {
  runtime_id: string;
  installed: boolean;
  version: string | null;
  reason: string | null;
  below_minimum: boolean;
  wanted_version: string | null;
  python_compatible: boolean;
  python_note: string | null;
  interpreter: string | null;
}

export interface Runtime {
  id: string;
  name: string;
  summary: string;
  homepage: string | null;
  serves: string[];
  backends: string[];
  license: string;
  runs: string[];
  notes: string | null;
  python_requires: string | null;
  install: { method: string; package: string; min_version: string | null; checked: string | null };
  status: RuntimeStatus;
  usable_here: boolean;
}

export interface RuntimeList {
  backend: string | null;
  chip: string | null;
  interpreter: string;
  runtimes: Runtime[];
}

export interface Impact {
  new: [string, string][];
  upgrades: [string, string, string][];
  downgrades: [string, string, string][];
  error: string | null;
  is_disruptive: boolean;
  command?: string;
  interpreter?: string;
}

export interface InstallJob {
  job_id: string;
  runtime_id: string;
  status: 'pending' | 'resolving' | 'installing' | 'completed' | 'failed' | 'refused';
  message: string | null;
  version: string | null;
  error: string | null;
  changed: Impact | null;
}

let cachedToken = '';
async function token(): Promise<string> {
  if (cachedToken) return cachedToken;
  const res = await fetch('/api/token');
  cachedToken = res.ok ? (await res.json()).token || '' : '';
  return cachedToken;
}

async function authed(path: string, init?: RequestInit) {
  const res = await fetch(path, {
    ...init,
    headers: { 'X-Pluto-Token': await token(), 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${await res.text().catch(() => '')}`.slice(0, 200));
  return res.json();
}

export function useRuntimes() {
  return useQuery<RuntimeList>({
    queryKey: ['runtimes'],
    queryFn: () => fetch('/api/runtimes').then((r) => {
      if (!r.ok) throw new Error('Failed to read runtimes');
      return r.json();
    }),
    staleTime: 15000,
  });
}

/** Resolve what an install would change. Never installs anything. */
export function usePreview() {
  const [state, setState] = useState<Record<string, Impact | 'loading' | undefined>>({});
  const run = useCallback(async (id: string) => {
    setState((s) => ({ ...s, [id]: 'loading' }));
    try {
      const impact: Impact = await authed(`/api/runtimes/${id}/preview`);
      setState((s) => ({ ...s, [id]: impact }));
    } catch (e) {
      setState((s) => ({
        ...s,
        [id]: { new: [], upgrades: [], downgrades: [], is_disruptive: false, error: String(e) },
      }));
    }
  }, []);
  const clear = useCallback((id: string) => setState((s) => ({ ...s, [id]: undefined })), []);
  return { previews: state, preview: run, clearPreview: clear };
}

/** Start an install and follow the job until it settles. */
export function useInstall() {
  const qc = useQueryClient();
  const [job, setJob] = useState<InstallJob | null>(null);
  const timer = useRef<number | null>(null);

  const stop = useCallback(() => {
    if (timer.current) { window.clearInterval(timer.current); timer.current = null; }
  }, []);

  useEffect(() => stop, [stop]);

  const start = useCallback(async (id: string, allowDowngrade: boolean) => {
    stop();
    const started: InstallJob = await authed(`/api/runtimes/${id}/install`, {
      method: 'POST',
      body: JSON.stringify({ allow_downgrade: allowDowngrade }),
    });
    setJob(started);

    timer.current = window.setInterval(async () => {
      try {
        const s: InstallJob = await authed(`/api/runtimes/jobs/${started.job_id}`);
        setJob(s);
        if (['completed', 'failed', 'refused'].includes(s.status)) {
          stop();
          // Re-read the list: a completed install changes what is present, and
          // a refusal does not, but re-reading is cheaper than reasoning about it.
          qc.invalidateQueries({ queryKey: ['runtimes'] });
        }
      } catch {
        /* a dropped poll is not a failed install; the next tick retries */
      }
    }, 900);
  }, [qc, stop]);

  return { job, start, reset: () => { stop(); setJob(null); } };
}
