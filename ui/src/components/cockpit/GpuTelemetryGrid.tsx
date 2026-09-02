import { useState, useEffect } from 'react';
import { Search, TrendingDown, Zap, Server, Activity, ShieldAlert } from 'lucide-react';

interface GpuTelemetryGridProps {
  instanceId?: string;
  instanceIp?: string;
  instanceType?: string;
  isOnline?: boolean;
  vramUsed?: number;
  vramTotal?: number;
  gpuLoad?: number;
  costPerHour?: number;
  totalCost?: number;
  sessionUptime?: number;
  savings?: number;
  onDemandRate?: number;
  initialUptimeMinutes?: number;
  onInspect?: () => void;
  idleShutdownMins?: number;
}

export function GpuTelemetryGrid({
  instanceId = 'i-spot-g6e-01',
  instanceIp = '198.51.100.24',
  instanceType = 'g6e.xlarge · us-east-1',
  isOnline = true,
  vramUsed = 18.4,
  vramTotal = 48.0,
  gpuLoad = 72,
  costPerHour = 0.75,
  onDemandRate = 1.75,
  initialUptimeMinutes = 18.5,
  onInspect,
  idleShutdownMins = 20,
}: GpuTelemetryGridProps) {
  // Live seconds-level elapsed uptime counter
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(initialUptimeMinutes * 60);

  useEffect(() => {
    setElapsedSeconds(initialUptimeMinutes * 60);
  }, [initialUptimeMinutes]);

  useEffect(() => {
    if (!isOnline) return;
    const interval = setInterval(() => {
      setElapsedSeconds(prev => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isOnline]);

  // Live billing calculations
  const totalCost = isOnline ? (elapsedSeconds / 3600) * costPerHour : 0;
  const onDemandCost = isOnline ? (elapsedSeconds / 3600) * onDemandRate : 0;
  const liveSavings = Math.max(0, onDemandCost - totalCost);
  const savingsPct = onDemandRate > 0 ? Math.round(((onDemandRate - costPerHour) / onDemandRate) * 100) : 57;

  // Format uptime
  const hours = Math.floor(elapsedSeconds / 3600);
  const minutes = Math.floor((elapsedSeconds % 3600) / 60);
  const seconds = Math.floor(elapsedSeconds % 60);
  const uptimeFriendly = hours > 0 ? `${hours}h ${minutes}m ${seconds}s` : `${minutes}m ${seconds}s`;

  const vramPercentage = Math.min(100, Math.round((vramUsed / (vramTotal || 48.0)) * 100));

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* 1. Instance Compute Card */}
      <div className="bg-inset border border-line-200 rounded-3xl p-6 flex flex-col justify-between gap-3.5 hover:border-line-400 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="w-3.5 h-3.5 text-ink-700" />
            <span className="font-mono text-[11px] font-semibold text-ink-500 uppercase tracking-wider">
              AWS EC2 Spot Compute
            </span>
          </div>
          <span className={`font-mono text-[11px] font-semibold px-2 py-0.5 rounded uppercase border ${
            isOnline
              ? 'bg-verify-soft text-verify border-verify/30'
              : 'bg-inset text-ink-500 border-line-200'
          }`}>
            {isOnline ? 'Running' : 'Offline'}
          </span>
        </div>

        <div className="font-mono text-[22px] sm:text-[24px] font-bold tracking-tight text-ink flex items-center justify-between truncate">
          <span className="truncate">{instanceId}</span>
          <button
            onClick={onInspect}
            disabled={!isOnline}
            className="font-sans text-[11px] font-semibold px-2.5 py-1 rounded-md border border-line-200 bg-inset text-ink hover:bg-strong hover:border-line-400 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
          >
            <Search className="w-3 h-3 text-ink-700" /> Inspect Box
          </button>
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-[13px] text-ink-700">
            <span>Public IP:</span>
            <span className="font-mono text-ink font-medium">{instanceIp}</span>
          </div>
          <div className="flex justify-between text-[13px] text-ink-700">
            <span>Type & Region:</span>
            <span className="font-mono text-ink font-medium">{instanceType}</span>
          </div>
        </div>
      </div>

      {/* 2. VRAM & Hardware Load Card */}
      <div className="bg-inset border border-line-200 rounded-3xl p-6 flex flex-col justify-between gap-3.5 hover:border-line-400 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-3.5 h-3.5 text-verify" />
            <span className="font-mono text-[11px] font-semibold text-ink-500 uppercase tracking-wider">
              GPU & VRAM Resident
            </span>
          </div>
          <span className={`font-mono text-[11px] font-semibold px-2 py-0.5 rounded uppercase border ${
            isOnline
              ? 'bg-verify-soft text-verify border-verify/30'
              : 'bg-inset text-ink-500 border-line-200'
          }`}>
            {isOnline ? `${gpuLoad}% Load` : 'Offline'}
          </span>
        </div>

        <div>
          <div className="font-mono text-[24px] font-bold tracking-tight text-ink">
            {isOnline ? `${vramUsed.toFixed(1)} / ${vramTotal.toFixed(1)} GiB` : '0.0 / 48.0 GiB'}
          </div>
          <div className="w-full h-1.5 bg-raised rounded-full overflow-hidden mt-2">
            <div
              className="h-full bg-verify transition-all duration-300"
              style={{ width: `${isOnline ? vramPercentage : 0}%` }}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-[13px] text-ink-700">
            <span>Accelerator Device:</span>
            <span className="font-mono text-ink font-medium">
              {isOnline ? 'NVIDIA L40S · 48GB GDDR6' : 'None'}
            </span>
          </div>
          <div className="flex justify-between text-[13px] text-ink-700">
            <span>VRAM Headroom:</span>
            <span className="font-mono text-verify font-medium">
              {isOnline ? `${Math.max(0, vramTotal - vramUsed).toFixed(1)} GiB Free` : '--'}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Live Billing & Cost Savings Odometer Card */}
      <div className="bg-inset border border-line-200 rounded-3xl p-6 flex flex-col justify-between gap-3.5 hover:border-line-400 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-3.5 h-3.5 text-verify" />
            <span className="font-mono text-[11px] font-semibold text-ink-500 uppercase tracking-wider">
              Live Billing Odometer
            </span>
          </div>
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-verify-soft text-verify border border-verify/30 uppercase flex items-center gap-1">
            <span>${costPerHour.toFixed(2)} / HR</span>
          </span>
        </div>

        {/* Odometer Animated Display */}
        <div className="flex items-baseline justify-between">
          <div className="flex flex-col">
            <div className="font-mono text-[28px] font-extrabold tracking-tight text-ink flex items-baseline gap-1">
              <span className="text-ink-700 text-[20px] font-bold">$</span>
              <span className="tabular-nums">
                {totalCost.toFixed(4)}
              </span>
            </div>
            <span className="text-[10.5px] font-mono text-ink-500 -mt-1">
              Live spot billing ticker (1s tick)
            </span>
          </div>

          {/* Savings Ticker Pill */}
          <div className="flex flex-col items-end bg-verify-soft border border-verify/25 px-2.5 py-1 rounded-lg">
            <span className="text-[10px] font-mono uppercase text-verify font-bold flex items-center gap-1">
              <Activity className="w-3 h-3 text-verify" /> Saved
            </span>
            <span className="font-mono text-[13px] font-bold text-verify tabular-nums">
              +${liveSavings.toFixed(3)}
            </span>
            <span className="text-[9.5px] font-mono text-verify/80">
              {savingsPct}% vs On-Demand
            </span>
          </div>
        </div>

        <div className="space-y-1.5 pt-1 border-t border-line-200">
          <div className="flex justify-between text-[13px] text-ink-700">
            <span>Session Uptime:</span>
            <span className="font-mono text-ink font-medium tabular-nums">
              {isOnline ? uptimeFriendly : '0m 0s'}
            </span>
          </div>
          <div className="flex justify-between text-[13px] text-ink-700">
            <span>Auto-Shutdown:</span>
            <span className="text-ink-900 font-medium flex items-center gap-1">
              <ShieldAlert className="w-3 h-3 text-ink-700" />
              {idleShutdownMins > 0 ? `${idleShutdownMins}m Idle Guard — will terminate` : 'Disabled'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

