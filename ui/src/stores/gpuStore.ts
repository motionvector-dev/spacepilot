import { create } from 'zustand';
import { api } from '../lib/api';

// null is "not reported", distinct from a real zero reading. See GpuStatusData
// in lib/api.ts for which of these /api/status actually carries.
export interface GpuStatus {
  online: boolean;
  instanceType: string | null;
  provider: 'aws_spot' | 'shadeform' | 'local';
  vramTotalGb: number | null;
  vramUsedGb: number | null;
  gpuUtilization: number | null;
  hourlyCostUsd: number | null;
  estimatedCostUsd: number | null;
  uptimeSeconds: number | null;
  deadManTimeoutSeconds: number | null;
  residentModel: string | null;
}

interface GpuState {
  status: GpuStatus;
  // Set when a status poll fails. The last `status` is then stale, not current.
  statusError: string | null;
  isLaunching: boolean;
  isTerminating: boolean;
  error: string | null;
  launchGpu: (confirm?: boolean) => Promise<void>;
  terminateGpu: (confirm?: boolean) => Promise<void>;
}

export const useGpuStore = create<GpuState>((set) => ({
  status: {
    online: false,
    instanceType: null,
    provider: 'aws_spot',
    vramTotalGb: null,
    vramUsedGb: null,
    gpuUtilization: null,
    hourlyCostUsd: null,
    estimatedCostUsd: null,
    uptimeSeconds: null,
    deadManTimeoutSeconds: null,
    residentModel: null,
  },
  statusError: null,
  isLaunching: false,
  isTerminating: false,
  error: null,
  launchGpu: async (confirm = true) => {
    set({ isLaunching: true, error: null });
    try {
      // launch is fire-and-backgrounded server-side (studio_api.py:487-493) — this only
      // confirms the request was accepted, not that the instance is up. Real
      // state comes from the status poller (useGpuPoller / useGpuStatus).
      await api.launchGpu(confirm);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ isLaunching: false });
    }
  },
  terminateGpu: async (confirm = true) => {
    set({ isTerminating: true, error: null });
    try {
      await api.terminateGpu(confirm);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ isTerminating: false });
    }
  },
}));
