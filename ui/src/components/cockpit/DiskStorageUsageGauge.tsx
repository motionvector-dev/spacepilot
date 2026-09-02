import { useState } from 'react';
import { HardDrive, Database, Trash2, Cpu, ArrowUpDown, CheckCircle2, RefreshCw } from 'lucide-react';
import { useInspectAction } from '../../hooks/useGpuStatus';

interface DiskStorageUsageGaugeProps {
  rootUsedGb?: number;
  rootTotalGb?: number;
  cacheUsedGb?: number;
  cacheTotalGb?: number;
  ramUsedGb?: number;
  ramTotalGb?: number;
  ioRateMbS?: number;
  onPurgeComplete?: () => void;
}

export function DiskStorageUsageGauge({
  rootUsedGb = 28.4,
  rootTotalGb = 100.0,
  cacheUsedGb = 142.5,
  cacheTotalGb = 500.0,
  ramUsedGb = 18.2,
  ramTotalGb = 64.0,
  ioRateMbS = 3800,
  onPurgeComplete,
}: DiskStorageUsageGaugeProps) {
  const [purged, setPurged] = useState(false);
  const inspectActionMutation = useInspectAction();

  const rootPct = Math.min(100, Math.round((rootUsedGb / rootTotalGb) * 100));
  const cachePct = Math.min(100, Math.round((cacheUsedGb / cacheTotalGb) * 100));
  const ramPct = Math.min(100, Math.round((ramUsedGb / ramTotalGb) * 100));

  const handlePurge = async () => {
    try {
      await inspectActionMutation.mutateAsync('clear_tmp');
      setPurged(true);
      onPurgeComplete?.();
      setTimeout(() => setPurged(false), 3000);
    } catch {
      // ignore
    }
  };

  const getBarColor = (pct: number) => {
    if (pct >= 90) return 'bg-danger';
    if (pct >= 75) return 'bg-strong';
    return 'bg-verify';
  };

  const getPctSuffix = (pct: number) => {
    if (pct >= 90) return ' full';
    if (pct >= 75) return ' tight';
    return '';
  };

  return (
    <div className="bg-inset border border-line-200 rounded-[24px] p-7 flex flex-col gap-6 hover:border-line-400 transition-all duration-150 ease-in-out">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-line-200 gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-inset border border-line-200">
            <HardDrive className="w-5 h-5 text-ink-700" />
          </div>
          <div>
            <h3 className="text-[17px] font-extrabold text-ink leading-tight">
              Storage &amp; Scratch Volumes Telemetry
            </h3>
            <p className="text-[12.5px] text-ink-700 mt-0.5">
              Real-time NVMe cache allocation, root SSD filesystem quotas, and resident host memory.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <div className="flex items-center gap-1.5 font-mono text-[11px] text-verify bg-verify-soft border border-verify/30 px-2.5 py-1 rounded-md">
            <ArrowUpDown className="w-3.5 h-3.5" />
            <span>{(ioRateMbS / 1024).toFixed(1)} GB/s NVMe Gen4 I/O</span>
          </div>

          <button
            onClick={handlePurge}
            disabled={inspectActionMutation.isPending}
            className={`font-sans text-xs font-semibold px-3 py-1.5 rounded-md border transition-all flex items-center gap-1.5 cursor-pointer ${
              purged
                ? 'bg-verify-soft text-verify border-verify/40'
                : 'bg-inset border-line-300 text-ink-700 hover:text-ink hover:bg-strong'
            }`}
            title="Purge scratch tmp directory to reclaim NVMe volume space"
          >
            {inspectActionMutation.isPending ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : purged ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-verify" />
            ) : (
              <Trash2 className="w-3.5 h-3.5 text-danger" />
            )}
            <span>{purged ? 'Purged' : 'Purge Tmp'}</span>
          </button>
        </div>
      </div>

      {/* 3 Storage Gauge Panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 1. SSD Root Filesystem */}
        <div className="bg-raised border border-line-200 rounded-2xl p-4 flex flex-col justify-between gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-ink-700" />
              <span className="font-mono text-[11px] font-semibold text-ink-500 uppercase tracking-wider">
                SSD Root Volume
              </span>
            </div>
            <span className="font-mono text-[11px] text-ink bg-inset px-2 py-0.5 rounded border border-line-200">
              Mount: /
            </span>
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="font-mono text-[20px] font-bold text-ink">
                {rootUsedGb.toFixed(1)} / {rootTotalGb.toFixed(1)} GB
              </span>
              <span className="font-mono text-[13px] font-semibold text-ink-700">
                {rootPct}%{getPctSuffix(rootPct)}
              </span>
            </div>

            <div className="w-full h-2 bg-inset rounded-full overflow-hidden">
              <div
                className={`h-full ${getBarColor(rootPct)} transition-all duration-300`}
                style={{ width: `${rootPct}%` }}
              />
            </div>
          </div>

          <div className="text-[11.5px] text-ink-500 flex justify-between font-mono">
            <span>Free: {(rootTotalGb - rootUsedGb).toFixed(1)} GB</span>
            <span className="text-ink-700">ext4 · OS &amp; Binaries</span>
          </div>
        </div>

        {/* 2. NVMe High-Speed Cache Volume */}
        <div className="bg-raised border border-line-200 rounded-2xl p-4 flex flex-col justify-between gap-3 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-verify" />
              <span className="font-mono text-[11px] font-semibold text-ink-500 uppercase tracking-wider">
                NVMe Scratch Cache
              </span>
            </div>
            <span className="font-mono text-[11px] text-verify bg-verify-soft px-2 py-0.5 rounded border border-verify/30">
              /mnt/pluto-cache
            </span>
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="font-mono text-[20px] font-bold text-ink">
                {cacheUsedGb.toFixed(1)} / {cacheTotalGb.toFixed(1)} GB
              </span>
              <span className="font-mono text-[13px] font-semibold text-ink-700">
                {cachePct}%{getPctSuffix(cachePct)}
              </span>
            </div>

            <div className="w-full h-2 bg-inset rounded-full overflow-hidden">
              <div
                className={`h-full ${getBarColor(cachePct)} transition-all duration-300`}
                style={{ width: `${cachePct}%` }}
              />
            </div>
          </div>

          <div className="text-[11.5px] text-ink-500 flex justify-between font-mono">
            <span>Free: {(cacheTotalGb - cacheUsedGb).toFixed(1)} GB</span>
            <span className="text-verify">Latents &amp; Model Weights</span>
          </div>
        </div>

        {/* 3. System RAM */}
        <div className="bg-raised border border-line-200 rounded-2xl p-4 flex flex-col justify-between gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-ink-700" />
              <span className="font-mono text-[11px] font-semibold text-ink-500 uppercase tracking-wider">
                Host System RAM
              </span>
            </div>
            <span className="font-mono text-[11px] text-ink bg-inset px-2 py-0.5 rounded border border-line-200">
              DDR5 / UMA
            </span>
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="font-mono text-[20px] font-bold text-ink">
                {ramUsedGb.toFixed(1)} / {ramTotalGb.toFixed(1)} GB
              </span>
              <span className="font-mono text-[13px] font-semibold text-ink-900">
                {ramPct}%
              </span>
            </div>

            <div className="w-full h-2 bg-inset rounded-full overflow-hidden">
              <div
                className="h-full bg-strong transition-all duration-300"
                style={{ width: `${ramPct}%` }}
              />
            </div>
          </div>

          <div className="text-[11.5px] text-ink-500 flex justify-between font-mono">
            <span>Free: {(ramTotalGb - ramUsedGb).toFixed(1)} GB</span>
            <span className="text-ink-700">Shared Memory Pool</span>
          </div>
        </div>
      </div>
    </div>
  );
}
