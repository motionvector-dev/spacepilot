/** The cockpit's read model.
 *
 * Every field here is returned by a route in `spacepilot/api/routes/`. Nothing
 * is derived from a constant, a default, or an assumption about the machine.
 * When a route does not report something the type says `null` and the screen
 * says so in words — see CONCEPT.md, "Honesty rules".
 */

export class DaemonDown extends Error {
  constructor(readonly path: string, cause?: unknown) {
    super(`the daemon did not answer ${path}`);
    this.name = 'DaemonDown';
    this.cause = cause;
  }
}

async function read<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { headers: { Accept: 'application/json' } });
  } catch (e) {
    throw new DaemonDown(path, e);
  }
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* a non-JSON error body is still an error */
    }
    throw new Error(`${path}: ${detail}`);
  }
  return (await res.json()) as T;
}

/* ------------------------------------------------------------------ ships */

/** GET /api/compute/local-profile — the machine this daemon runs on. */
export interface LocalProfile {
  machine_name: string | null;
  machine_model: string | null;
  chip: string | null;
  backend: string | null;
  backend_detail: string | null;
  os_name: string | null;
  os_version: string | null;
  arch: string | null;
  cpu_cores: number | null;
  gpu_cores: number | null;
  gpu_name: string | null;
  memory_total_bytes: number | null;
  memory_free_bytes: number | null;
  memory_limit_bytes: number | null;
  memory_limit_source: string | null;
  memory_unified: boolean;
  disk_free_bytes: number | null;
  disk_path: string | null;
  vram_usable_gb: number | null;
  usable_memory_known: boolean;
  is_local_capable: boolean;
  status: string | null;
}

/** GET /api/systems — every machine the corpus has ever probed, this one or not. */
export interface SystemRecord {
  id: string;
  chip: string | null;
  machine_model: string | null;
  backend: string | null;
  os_name: string | null;
  os_version: string | null;
  cpu_cores: number | null;
  gpu_cores: number | null;
  memory_total_bytes: number | null;
  memory_limit_bytes: number | null;
  recorded_on: string | null;
  host_fingerprint: string | null;
}

/* ------------------------------------------------------------------ docks */

/** GET /api/cockpit/status — the rented box, whether or not one is running. */
export interface DockStatus {
  instance: { id?: string; ip?: string; state?: string; launched_at?: string } | null;
  gpu_online: boolean;
  worker_ready: boolean;
  uptime_minutes: number | null;
  estimated_cost_usd: number | null;
  message: string | null;
  ssh_command: string | null;
  config: {
    region: string | null;
    instance_type: string | null;
    spot_hourly_rate: number | null;
    key_file: string | null;
  };
}

/* --------------------------------------------------------------- runtimes */

export interface RuntimeStatus {
  installed: boolean;
  version: string | null;
  reason: string | null;
  below_minimum: boolean;
  wanted_version: string | null;
  python_compatible: boolean;
}

export interface RuntimeRow {
  id: string;
  name: string;
  summary: string | null;
  serves: string[];
  backends: string[];
  license: string | null;
  runs: string[];
  status: RuntimeStatus;
  usable_here: boolean;
}

export interface RuntimesPayload {
  backend: string | null;
  chip: string | null;
  interpreter: string | null;
  runtimes: RuntimeRow[];
}

/* --------------------------------------------------------- model verdicts */

export type Verdict = 'fits' | 'tight' | 'wont_fit' | string;

export interface ModelVerdict {
  recipe_id: string;
  verdict: Verdict;
  reason: string | null;
  footprint: string | null;
  memory_use_ratio: number | null;
  runnable_now: boolean;
  disk_ok: boolean;
}

export interface ModelRecipe {
  recipe_id: string;
  name: string;
  family: string | null;
  kind: string | null;
  params: string | null;
  quantization: string | null;
  is_local_runnable: boolean;
}

export interface CompatibilityReport {
  device: LocalProfile;
  models: ModelRecipe[];
  verdicts: Record<string, ModelVerdict>;
  recommended: string | null;
  installed: string[];
}

/* ---------------------------------------------------------- flown numbers */

/** GET /api/summary. `provenance` is the honesty field: never blend the two. */
export interface FlownSummary {
  system_id: string;
  model_id: string;
  metric: string;
  solo_median: number | null;
  solo_samples: number;
  observed_median: number | null;
  observed_samples: number;
  failed_samples: number;
  provenance: 'flown' | 'on_paper' | 'unflown' | string;
  observed_latest_on: string | null;
  solo_latest_on: string | null;
  caveats: string[];
}

export const fleet = {
  profile: () => read<LocalProfile>('/api/compute/local-profile'),
  systems: () => read<{ systems: SystemRecord[] }>('/api/systems'),
  dock: () => read<DockStatus>('/api/cockpit/status'),
  runtimes: () => read<RuntimesPayload>('/api/runtimes'),
  compatibility: () => read<CompatibilityReport>('/api/compute/compatibility'),
  summary: () => read<{ summaries: FlownSummary[] }>('/api/summary'),
};

/* --------------------------------------------------------------- formatting */

/** Bytes to GB. `null` in, `null` out — never 0, which reads as a measurement. */
export function gb(bytes: number | null | undefined): number | null {
  if (bytes === null || bytes === undefined) return null;
  return bytes / 1024 ** 3;
}

export function fmtGb(bytes: number | null | undefined, digits = 1): string | null {
  const v = gb(bytes);
  return v === null ? null : `${v.toFixed(digits)} GB`;
}

/** The age every live fact has to carry. CONCEPT.md: a stale "ready" is a lie. */
export function age(at: number | undefined, now: number): string {
  if (!at) return 'not yet checked';
  const s = Math.max(0, Math.round((now - at) / 1000));
  if (s < 60) return `checked ${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `checked ${m}m ago`;
  return `checked ${Math.round(m / 60)}h ago`;
}

/** A machine record and the live probe are the same machine when the chip and
 *  the memory ceiling agree. The corpus has no host id for the live probe. */
export function matchesLiveMachine(s: SystemRecord, p: LocalProfile | undefined): boolean {
  if (!p) return false;
  return s.chip === p.chip && s.memory_total_bytes === p.memory_total_bytes;
}
