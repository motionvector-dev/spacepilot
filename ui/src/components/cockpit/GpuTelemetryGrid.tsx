
import { Search } from 'lucide-react';

interface GpuTelemetryGridProps {
  instanceId?: string;
  instanceIp?: string;
  instanceType?: string;
  vramUsed?: number;
  vramTotal?: number;
  gpuLoad?: number;
  costPerHour?: number;
  totalCost?: number;
  sessionUptime?: number;
  savings?: number;
}

export function GpuTelemetryGrid({
  instanceId = 'i-0a1b2c3d4e5f6g7h8',
  instanceIp = '198.51.100.24',
  instanceType = 'g6e.xlarge · us-east-1',
  vramUsed = 18.4,
  vramTotal = 48.0,
  gpuLoad = 87,
  costPerHour = 0.75,
  totalCost = 1.25,
  sessionUptime = 100,
  savings = 4.50
}: GpuTelemetryGridProps) {
  const vramPercentage = (vramUsed / vramTotal) * 100;
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Instance Card */}
      <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 flex flex-col gap-3.5">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] font-semibold text-[#71717a] uppercase tracking-wider">
            AWS EC2 Spot Compute
          </span>
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/30 uppercase">
            Online
          </span>
        </div>
        <div className="font-mono text-[26px] font-bold tracking-tight text-[#fafafa] flex items-center justify-between">
          <span>{instanceId}</span>
          <button className="font-sans text-[11px] font-semibold px-2 py-1 rounded-md border border-white/10 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/20 transition-all flex items-center gap-1.5 cursor-pointer">
            <Search className="w-3 h-3" /> Inspect Box
          </button>
        </div>
        <div className="flex justify-between text-[13px] text-[#a1a1aa]">
          <span>Public IP:</span>
          <span className="font-mono text-[#fafafa] font-medium">{instanceIp}</span>
        </div>
        <div className="flex justify-between text-[13px] text-[#a1a1aa]">
          <span>Type & Region:</span>
          <span className="font-mono text-[#fafafa] font-medium">{instanceType}</span>
        </div>
      </div>

      {/* VRAM Card */}
      <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 flex flex-col gap-3.5">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] font-semibold text-[#71717a] uppercase tracking-wider">
            GPU & VRAM Resident
          </span>
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/30 uppercase">
            {gpuLoad}% Load
          </span>
        </div>
        <div className="font-mono text-[26px] font-bold tracking-tight text-[#fafafa]">
          {vramUsed.toFixed(1)} / {vramTotal.toFixed(1)} GiB
        </div>
        <div className="w-full h-1.5 bg-[#111114] rounded-full overflow-hidden">
          <div 
            className="h-full bg-[#10b981] transition-all duration-300"
            style={{ width: `${vramPercentage}%` }}
          />
        </div>
        <div className="flex justify-between text-[13px] text-[#a1a1aa]">
          <span>Device:</span>
          <span className="font-mono text-[#fafafa] font-medium">NVIDIA L40S</span>
        </div>
      </div>

      {/* Cost & Billing Card */}
      <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 flex flex-col gap-3.5">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] font-semibold text-[#71717a] uppercase tracking-wider">
            Live Billing Odometer
          </span>
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-white/5 text-[#a1a1aa] border border-white/10 uppercase">
            ${costPerHour.toFixed(2)} / HR
          </span>
        </div>
        <div className="font-mono text-[26px] font-bold tracking-tight text-[#fafafa] flex items-center justify-between">
          <span>${totalCost.toFixed(2)}</span>
          <span className="text-[13px] font-medium text-[#10b981] flex flex-col items-end leading-tight">
            <span>Savings</span>
            <span>+${savings.toFixed(2)}</span>
          </span>
        </div>
        <div className="flex justify-between text-[13px] text-[#a1a1aa]">
          <span>Session Uptime:</span>
          <span className="font-mono text-[#fafafa] font-medium">{sessionUptime} mins</span>
        </div>
        <div className="flex justify-between text-[13px] text-[#a1a1aa]">
          <span>Auto-Shutdown:</span>
          <span className="text-[#f59e0b] font-medium">20m Idle Guard</span>
        </div>
      </div>
    </div>
  );
}
