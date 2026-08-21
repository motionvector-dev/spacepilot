import { useEffect } from 'react';
import { useGpuStore } from '../stores/gpuStore';
import { api } from '../lib/api';

export function useGpuPoller(intervalMs = 5000) {
  const { isLaunching } = useGpuStore();

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;

    const poll = async () => {
      try {
        const data = await api.getGpuStatus();
        useGpuStore.setState({
          status: {
            instanceType: data.instance_type,
            provider: data.provider as 'aws_spot' | 'shadeform' | 'local',
            vramTotalGb: data.vram_total_gb,
            vramUsedGb: data.vram_used_gb,
            gpuUtilization: data.gpu_utilization,
            hourlyCostUsd: data.hourly_cost,
            uptimeSeconds: data.uptime_seconds,
            deadManTimeoutSeconds: data.dead_man_seconds_remaining,
            residentModel: 'ltx-2.5-float8',
          }
        });
      } catch (err) {
        // Fallback to state if backend offline during dev
      }
    };

    poll();
    timer = setInterval(poll, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, isLaunching]);
}
