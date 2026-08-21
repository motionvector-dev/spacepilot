
import { RefreshCw } from 'lucide-react';

interface CockpitHeaderProps {
  onRefresh?: () => void;
  status?: 'online' | 'offline' | 'connecting';
  countdownMinutes?: number;
}

export function CockpitHeader({ 
  onRefresh, 
  status = 'online',
  countdownMinutes = 20
}: CockpitHeaderProps) {
  return (
    <div className="flex items-end justify-between pb-6 border-b border-white/10">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-[28px] font-bold tracking-tight text-[#fafafa]">
            Autonomous GPU Spot Cockpit
          </h1>
          <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#a1a1aa] bg-[#111114] border border-white/10 px-2.5 py-1 rounded-full">
            <span className={`w-1.5 h-1.5 rounded-full ${status === 'online' ? 'bg-[#10b981] shadow-[0_0_6px_#10b981]' : status === 'offline' ? 'bg-[#71717a]' : 'bg-[#f59e0b] animate-pulse'}`} />
            <span>HUD {status.toUpperCase()}</span>
          </div>
          {status === 'online' && (
            <div className="flex items-center gap-1.5 font-mono text-[11px] text-[#f59e0b] bg-[#111114] border border-white/10 px-2.5 py-1 rounded-full">
              <span>⏱ {countdownMinutes}m DEAD MAN'S SWITCH</span>
            </div>
          )}
        </div>
        <p className="text-sm text-[#a1a1aa]">
          Multi-cloud broker telemetry, resident VRAM watchdog, and zero-data-loss spot orchestration.
        </p>
      </div>
      <button 
        onClick={onRefresh}
        className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/10 bg-[#18181b] text-[#fafafa] cursor-pointer inline-flex items-center gap-2 transition-all duration-150 hover:bg-[#222226] hover:border-white/20"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>Refresh State</span>
      </button>
    </div>
  );
}
