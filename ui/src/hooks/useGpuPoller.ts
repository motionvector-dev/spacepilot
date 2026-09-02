import { useEffect } from 'react';
import { useGpuStore } from '../stores/gpuStore';
import { api } from '../lib/api';

export function useGpuPoller(intervalMs = 4000) {
  const { isLaunching } = useGpuStore();

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;

    const poll = async () => {
      try {
        const data = await api.getGpuStatus();
        useGpuStore.setState({
          statusError: null,
          status: {
            online: data.online,
            instanceType: data.instance_type,
            provider: data.provider,
            vramTotalGb: data.vram_total_gb,
            vramUsedGb: data.vram_used_gb,
            gpuUtilization: data.gpu_utilization,
            hourlyCostUsd: data.hourly_cost,
            estimatedCostUsd: data.estimated_cost_usd,
            uptimeSeconds: data.uptime_seconds,
            deadManTimeoutSeconds: data.dead_man_seconds_remaining,
            residentModel: data.resident_model,
          },
        });
      } catch (err) {
        // Surface the failure rather than leaving the last snapshot on screen
        // looking current — an unreachable server is an unknown GPU, not an idle one.
        useGpuStore.setState({
          statusError: err instanceof Error ? err.message : String(err),
        });
      }
    };

    poll();
    timer = setInterval(poll, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, isLaunching]);
}
