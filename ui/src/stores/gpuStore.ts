import { create } from 'zustand';
import { fetchToken } from '../hooks/useGpuStatus';

export interface GpuStatus {
  instanceType: string;
  provider: 'aws_spot' | 'shadeform' | 'local';
  vramTotalGb: number;
  vramUsedGb: number;
  gpuUtilization: number;
  hourlyCostUsd: number;
  uptimeSeconds: number;
  deadManTimeoutSeconds: number;
  residentModel: string;
}

interface GpuState {
  status: GpuStatus;
  isLaunching: boolean;
  isTerminating: boolean;
  error: string | null;
  launchGpu: (confirm?: boolean) => Promise<void>;
  terminateGpu: (confirm?: boolean) => Promise<void>;
}

// gpu.py's /api/gpu/launch and /api/gpu/terminate both 400 without {confirm: true}
// in the body, and both require X-Pluto-Token (Depends(require_token)).
async function postGpuAction(endpoint: '/api/gpu/launch' | '/api/gpu/terminate', confirm: boolean) {
  const token = await fetchToken();
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Pluto-Token': token } : {}),
    },
    body: JSON.stringify({ confirm }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail || data?.message || `${endpoint} failed (${res.status})`);
  }
  return data as { status?: string; message?: string };
}

export const useGpuStore = create<GpuState>((set) => ({
  status: {
    instanceType: 'g6e.xlarge',
    provider: 'aws_spot',
    vramTotalGb: 48,
    vramUsedGb: 0,
    gpuUtilization: 0,
    hourlyCostUsd: 0.75,
    uptimeSeconds: 0,
    deadManTimeoutSeconds: 1800,
    residentModel: 'ltx-2.5-float8',
  },
  isLaunching: false,
  isTerminating: false,
  error: null,
  launchGpu: async (confirm = true) => {
    set({ isLaunching: true, error: null });
    try {
      // launch is fire-and-backgrounded server-side (gpu.py:71-77) — this only
      // confirms the request was accepted, not that the instance is up. Real
      // state comes from the status poller (useGpuPoller / useGpuStatus).
      await postGpuAction('/api/gpu/launch', confirm);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ isLaunching: false });
    }
  },
  terminateGpu: async (confirm = true) => {
    set({ isTerminating: true, error: null });
    try {
      await postGpuAction('/api/gpu/terminate', confirm);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ isTerminating: false });
    }
  },
}));
