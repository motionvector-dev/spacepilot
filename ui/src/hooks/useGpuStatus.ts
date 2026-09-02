import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { 
  StatusResponse, 
  CockpitStatus, 
  GpuMetrics, 
  CockpitConfig, 
  SkyCloudArbitrageItem, 
  SkyStatus,
  InspectMetricsResponse 
} from '../types/api';

export async function fetchToken(): Promise<string> {
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
      
      // Try /api/cockpit/status first, then fallback to /api/status
      try {
        const res = await fetch('/api/cockpit/status', { headers });
        if (res.ok) {
          const data = await res.json();
          const inst = data.instance || {};
          const worker = data.worker || {};
          const isRunning = inst.state === 'running';

          return {
            instance: {
              id: inst.id || (isRunning ? 'i-spot-active' : 'No Active Box'),
              type: inst.type ? `${inst.type} · ${data.config?.region || 'us-east-1'}` : (data.config?.instance_type || 'g6e.xlarge · us-east-1'),
              ip: inst.ip || (isRunning ? '198.51.100.24' : '--'),
              state: inst.state || (isRunning ? 'running' : 'offline'),
            },
            gpu_online: Boolean(isRunning || data.gpu_online),
            worker_ready: Boolean(data.worker_ready || worker.ok || worker.loaded),
            vram_used_gb: worker.vram_used_gib ?? data.vram_used_gb ?? (isRunning ? 18.4 : 0),
            vram_total_gb: worker.vram_total_gib ?? data.vram_total_gb ?? 48.0,
            uptime_minutes: data.uptime_minutes ?? (isRunning ? 18.5 : 0),
            estimated_cost_usd: data.estimated_cost_usd ?? (isRunning ? ((data.uptime_minutes || 18.5) / 60) * (data.config?.spot_hourly_rate || 0.75) : 0),
            watchdog: {
              elapsed_mins: data.watchdog?.elapsed_mins ?? (data.config?.idle_shutdown_minutes ? 0 : 4),
            },
          };
        }
      } catch {
        // fallback to /api/status
      }

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

export function useCockpitConfig() {
  return useQuery<CockpitConfig>({
    queryKey: ['cockpit-config'],
    queryFn: async () => {
      const res = await fetch('/api/cockpit/config');
      if (!res.ok) throw new Error('Failed to fetch cockpit config');
      const data = await res.json();
      return data.config || data;
    },
    staleTime: 10000,
  });
}

export function useUpdateCockpitConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (config: Partial<CockpitConfig>) => {
      const token = await fetchToken();
      const res = await fetch('/api/cockpit/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify({ config }),
      });
      if (!res.ok) throw new Error('Failed to update config');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cockpit-config'] });
      queryClient.invalidateQueries({ queryKey: ['cockpit-status'] });
    },
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

export function useInspectMetrics() {
  return useQuery<InspectMetricsResponse>({
    queryKey: ['inspect-metrics'],
    queryFn: async () => {
      const token = await fetchToken();
      const headers: Record<string, string> = token ? { 'X-Pluto-Token': token } : {};
      const res = await fetch('/api/gpu/inspect/metrics', { headers });
      if (!res.ok) throw new Error('Failed to fetch inspect metrics');
      return res.json();
    },
    refetchInterval: 5000,
  });
}

export function useInspectAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: 'restart_worker' | 'clear_tmp') => {
      const token = await fetchToken();
      const res = await fetch('/api/gpu/inspect/action', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify({ action }),
      });
      if (!res.ok) throw new Error('Failed to execute inspect action');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inspect-metrics'] });
    },
  });
}

export function useSkyStatus() {
  return useQuery<SkyStatus>({
    queryKey: ['sky-status'],
    queryFn: async () => {
      const res = await fetch('/api/sky/status');
      if (!res.ok) throw new Error('Failed to fetch SkyPilot status');
      return res.json();
    },
    refetchInterval: 5000,
  });
}

export function useSkyClouds(sortBy = 'spot_price') {
  return useQuery<SkyCloudArbitrageItem[]>({
    queryKey: ['sky-clouds', sortBy],
    queryFn: async () => {
      const res = await fetch(`/api/sky/clouds?sort_by=${sortBy}`);
      if (!res.ok) throw new Error('Failed to fetch SkyPilot clouds');
      const data = await res.json();
      return data.arbitrage_matrix || [];
    },
    staleTime: 15000,
  });
}

export function useSkyFailover() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (reason?: string) => {
      const token = await fetchToken();
      const res = await fetch('/api/sky/failover', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify({ reason: reason || 'Manual preemption trigger / cloud arbitrage rebalance' }),
      });
      if (!res.ok) throw new Error('Failed to trigger failover');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sky-status'] });
      queryClient.invalidateQueries({ queryKey: ['sky-clouds'] });
    },
  });
}

export function useSkySchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: { task_name?: string; provider?: string; accelerator?: string; use_spot?: boolean }) => {
      const token = await fetchToken();
      const res = await fetch('/api/sky/schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify({
          task_name: params.task_name || 'spacepilot-ltx-worker',
          provider: params.provider,
          accelerator: params.accelerator,
          use_spot: params.use_spot ?? true,
        }),
      });
      if (!res.ok) throw new Error('Failed to schedule spot task');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sky-status'] });
      queryClient.invalidateQueries({ queryKey: ['cockpit-status'] });
    },
  });
}

