import { useQuery } from '@tanstack/react-query';
import type { StatusResponse, CockpitStatus, GpuMetrics } from '../types/api';

async function fetchToken(): Promise<string> {
  try {
    const res = await fetch('/api/token');
    if (res.ok) {
      const data = await res.json();
      return data.token || '';
    }
  } catch {
    // ignore
  }
  return '';
}

export function useGpuStatus() {
  return useQuery<StatusResponse>({
    queryKey: ['gpu-status'],
    queryFn: async () => {
      const res = await fetch('/api/status');
      if (!res.ok) throw new Error('Failed to fetch status');
      return res.json();
    },
    refetchInterval: 3000,
  });
}

export function useCockpitTelemetry() {
  return useQuery<CockpitStatus>({
    queryKey: ['cockpit-status'],
    queryFn: async () => {
      const token = await fetchToken();
      const headers: Record<string, string> = token ? { 'X-Pluto-Token': token } : {};
      
      const res = await fetch('/api/status', { headers });
      if (!res.ok) throw new Error('Failed to fetch cockpit status');
      const data = await res.json();

      return {
        instance: {
          id: data.instance?.id || 'i-spot-g6e-01',
          type: data.instance?.type || 'g6e.xlarge · us-east-1',
          ip: data.instance?.ip || '127.0.0.1',
          state: data.gpu_online ? 'running' : 'offline',
        },
        gpu_online: Boolean(data.gpu_online),
        worker_ready: Boolean(data.worker_ready),
        vram_used_gb: data.vram_used_gb ?? (data.gpu_online ? 18.4 : 0),
        vram_total_gb: data.vram_total_gb ?? 48.0,
        uptime_minutes: data.uptime_minutes ?? 0,
        estimated_cost_usd: data.estimated_cost_usd ?? (data.uptime_minutes ? (data.uptime_minutes / 60) * 0.75 : 0),
        watchdog: {
          elapsed_mins: data.watchdog?.elapsed_mins ?? 0,
        },
      };
    },
    refetchInterval: 3000,
  });
}

export function useGpuMetrics() {
  return useQuery<GpuMetrics>({
    queryKey: ['gpu-metrics'],
    queryFn: async () => {
      const token = await fetchToken();
      const headers: Record<string, string> = token ? { 'X-Pluto-Token': token } : {};
      const res = await fetch('/api/gpu/inspect/metrics', { headers });
      if (!res.ok) throw new Error('Failed to fetch GPU metrics');
      return res.json();
    },
    refetchInterval: 2500,
  });
}
