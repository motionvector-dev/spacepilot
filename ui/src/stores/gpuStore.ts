import { create } from 'zustand';

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
  launchGpu: () => Promise<void>;
  terminateGpu: () => Promise<void>;
}

export const useGpuStore = create<GpuState>((set) => ({
  status: {
    instanceType: 'g6e.xlarge',
    provider: 'aws_spot',
    vramTotalGb: 48,
    vramUsedGb: 18.4,
    gpuUtilization: 42,
    hourlyCostUsd: 0.75,
    uptimeSeconds: 1420,
    deadManTimeoutSeconds: 1800,
    residentModel: 'ltx-2.5-float8',
  },
  isLaunching: false,
  launchGpu: async () => {
    set({ isLaunching: true });
    // In production, calls /api/gpu/launch
    setTimeout(() => {
      set({ isLaunching: false });
    }, 1500);
  },
  terminateGpu: async () => {
    // In production, calls /api/gpu/terminate
  }
}));
