import type { GpuStatus } from '../stores/gpuStore';

/** Renders unreported telemetry as an em dash so a missing reading never
 *  reads as a real zero. */
export function formatVram(status: GpuStatus): string {
  const { vramUsedGb, vramTotalGb } = status;
  if (vramUsedGb === null || vramTotalGb === null) return 'VRAM —';
  return `${vramUsedGb.toFixed(1)} / ${vramTotalGb}GB`;
}

export function formatAccruedCost(status: GpuStatus): string {
  return status.estimatedCostUsd === null ? '—' : `$${status.estimatedCostUsd.toFixed(2)}`;
}

/** Three states, not two: unknown (poll failed), online, stopped. */
export function gpuDotClass(status: GpuStatus, statusError: string | null): string {
  if (statusError) return 'bg-amber-400';
  return status.online ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600';
}

export function gpuLabel(status: GpuStatus, statusError: string | null): string {
  if (statusError) return 'GPU STATUS UNKNOWN';
  if (!status.online) return 'GPU STOPPED';
  return status.instanceType ? status.instanceType.toUpperCase() : 'GPU ONLINE';
}
