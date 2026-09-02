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
      <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 flex flex-col justify-between gap-3.5 hover:border-white/20 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="w-3.5 h-3.5 text-[#a1a1aa]" />
            <span className="font-mono text-[11px] font-semibold text-[#71717a] uppercase tracking-wider">
              AWS EC2 Spot Compute
            </span>
          </div>
          <span className={`font-mono text-[11px] font-semibold px-2 py-0.5 rounded uppercase border ${
            isOnline 
              ? 'bg-[#10b981]/10 text-[#10b981] border-[#10b981]/30' 
              : 'bg-white/5 text-[#71717a] border-white/10'
          }`}>
            {isOnline ? 'Running' : 'Offline'}
          </span>
        </div>

        <div className="font-mono text-[22px] sm:text-[24px] font-bold tracking-tight text-[#fafafa] flex items-center justify-between truncate">
          <span className="truncate">{instanceId}</span>
          <button 
            onClick={onInspect}
            disabled={!isOnline}
            className="font-sans text-[11px] font-semibold px-2.5 py-1 rounded-md border border-white/10 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/20 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
          >
            <Search className="w-3 h-3 text-[#3b82f6]" /> Inspect Box
          </button>
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-[13px] text-[#a1a1aa]">
            <span>Public IP:</span>
            <span className="font-mono text-[#fafafa] font-medium">{instanceIp}</span>
          </div>
          <div className="flex justify-between text-[13px] text-[#a1a1aa]">
            <span>Type & Region:</span>
            <span className="font-mono text-[#fafafa] font-medium">{instanceType}</span>
          </div>
        </div>
      </div>

      {/* 2. VRAM & Hardware Load Card */}
      <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 flex flex-col justify-between gap-3.5 hover:border-white/20 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-3.5 h-3.5 text-[#10b981]" />
            <span className="font-mono text-[11px] font-semibold text-[#71717a] uppercase tracking-wider">
              GPU & VRAM Resident
            </span>
          </div>
          <span className={`font-mono text-[11px] font-semibold px-2 py-0.5 rounded uppercase border ${
            isOnline 
              ? 'bg-[#10b981]/10 text-[#10b981] border-[#10b981]/30' 
              : 'bg-white/5 text-[#71717a] border-white/10'
          }`}>
            {isOnline ? `${gpuLoad}% Load` : 'Offline'}
          </span>
        </div>

        <div>
          <div className="font-mono text-[24px] font-bold tracking-tight text-[#fafafa]">
            {isOnline ? `${vramUsed.toFixed(1)} / ${vramTotal.toFixed(1)} GiB` : '0.0 / 48.0 GiB'}
          </div>
          <div className="w-full h-1.5 bg-[#111114] rounded-full overflow-hidden mt-2">
            <div 
              className="h-full bg-[#10b981] transition-all duration-300 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
              style={{ width: `${isOnline ? vramPercentage : 0}%` }}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-[13px] text-[#a1a1aa]">
            <span>Accelerator Device:</span>
            <span className="font-mono text-[#fafafa] font-medium">
              {isOnline ? 'NVIDIA L40S · 48GB GDDR6' : 'None'}
            </span>
          </div>
          <div className="flex justify-between text-[13px] text-[#a1a1aa]">
            <span>VRAM Headroom:</span>
            <span className="font-mono text-[#10b981] font-medium">
              {isOnline ? `${Math.max(0, vramTotal - vramUsed).toFixed(1)} GiB Free` : '--'}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Live Billing & Cost Savings Odometer Card */}
      <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 flex flex-col justify-between gap-3.5 hover:border-white/20 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-3.5 h-3.5 text-[#10b981]" />
            <span className="font-mono text-[11px] font-semibold text-[#71717a] uppercase tracking-wider">
              Live Billing Odometer
            </span>
          </div>
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/30 uppercase flex items-center gap-1">
            <span>${costPerHour.toFixed(2)} / HR</span>
          </span>
        </div>

        {/* Odometer Animated Display */}
        <div className="flex items-baseline justify-between">
          <div className="flex flex-col">
            <div className="font-mono text-[28px] font-extrabold tracking-tight text-[#fafafa] flex items-baseline gap-1">
              <span className="text-[#a1a1aa] text-[20px] font-bold">$</span>
              <span className="tabular-nums drop-shadow-sm">
                {totalCost.toFixed(4)}
              </span>
            </div>
            <span className="text-[10.5px] font-mono text-[#71717a] -mt-1">
              Live spot billing ticker (1s tick)
            </span>
          </div>

          {/* Savings Ticker Pill */}
          <div className="flex flex-col items-end bg-[#10b981]/10 border border-[#10b981]/25 px-2.5 py-1 rounded-lg">
            <span className="text-[10px] font-mono uppercase text-[#10b981] font-bold flex items-center gap-1">
              <Activity className="w-3 h-3 text-[#10b981]" /> Saved
            </span>
            <span className="font-mono text-[13px] font-bold text-[#10b981] tabular-nums">
              +${liveSavings.toFixed(3)}
            </span>
            <span className="text-[9.5px] font-mono text-[#10b981]/80">
              {savingsPct}% vs On-Demand
            </span>
          </div>
        </div>

        <div className="space-y-1.5 pt-1 border-t border-white/5">
          <div className="flex justify-between text-[13px] text-[#a1a1aa]">
            <span>Session Uptime:</span>
            <span className="font-mono text-[#fafafa] font-medium tabular-nums">
              {isOnline ? uptimeFriendly : '0m 0s'}
            </span>
          </div>
          <div className="flex justify-between text-[13px] text-[#a1a1aa]">
            <span>Auto-Shutdown:</span>
            <span className="text-[#f59e0b] font-medium flex items-center gap-1">
              <ShieldAlert className="w-3 h-3 text-[#f59e0b]" />
              {idleShutdownMins > 0 ? `${idleShutdownMins}m Idle Guard` : 'Disabled'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

