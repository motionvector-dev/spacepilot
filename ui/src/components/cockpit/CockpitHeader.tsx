import { useState, useEffect } from 'react';
import { RefreshCw, Clock, Plus, ShieldCheck, AlertCircle } from 'lucide-react';

interface CockpitHeaderProps {
  onRefresh?: () => void;
  status?: 'online' | 'offline' | 'connecting' | 'launching';
  countdownMinutes?: number;
  onExtendWatchdog?: (additionalMins: number) => void;
  onResetWatchdog?: () => void;
  isExtending?: boolean;
}

export function CockpitHeader({ 
  onRefresh, 
  status = 'online',
  countdownMinutes = 20,
  onExtendWatchdog,
  onResetWatchdog,
  isExtending = false,
}: CockpitHeaderProps) {
  // Live local countdown ticker for seconds precision
  const [remainingSeconds, setRemainingSeconds] = useState<number>(countdownMinutes * 60);

  useEffect(() => {
    setRemainingSeconds(countdownMinutes * 60);
  }, [countdownMinutes]);

  useEffect(() => {
    if (status !== 'online') return;
    const interval = setInterval(() => {
      setRemainingSeconds(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [status]);

  const mins = Math.floor(remainingSeconds / 60);
  const secs = remainingSeconds % 60;
  const formattedTime = `${mins}m ${secs.toString().padStart(2, '0')}s`;
  const isUrgent = remainingSeconds > 0 && remainingSeconds <= 300; // Under 5 minutes

  return (
    <div className="flex flex-col md:flex-row md:items-end justify-between pb-6 border-b border-line-200 gap-4">
      <div>
        <div className="flex items-center gap-3 mb-1 flex-wrap">
          <h1 className="text-[28px] font-bold tracking-tight text-ink">
            Autonomous GPU Spot Cockpit
          </h1>
          <div className="flex items-center gap-1.5 font-mono text-[11px] text-ink-700 bg-raised border border-line-200 px-2.5 py-1 rounded-full">
            <span className={`w-1.5 h-1.5 rounded-full ${
              status === 'online' ? 'bg-verify' :
              status === 'offline' ? 'bg-ink-500' :
              'bg-ink-500 animate-pulse'
            }`} />
            <span>HUD {status.toUpperCase()}</span>
          </div>

          {/* Dead Man's Switch Live Countdown Pill */}
          {status === 'online' && (
            <div className={`flex items-center gap-1.5 font-mono text-[11px] px-2.5 py-1 rounded-full border transition-all ${
              isUrgent
                ? 'bg-danger-soft text-danger border-danger animate-pulse'
                : 'bg-raised text-ink-700 border-line-200'
            }`}>
              {isUrgent ? <AlertCircle className="w-3.5 h-3.5 text-danger" /> : <Clock className="w-3.5 h-3.5 text-ink-700" />}
              <span>⏱ {formattedTime} AUTO-SHUTDOWN</span>
            </div>
          )}
        </div>
        <p className="text-sm text-ink-700">
          Multi-cloud broker telemetry, resident VRAM watchdog, and zero-data-loss spot orchestration.
        </p>
      </div>

      {/* Header Actions: Dead Man's Switch Extend + Refresh */}
      <div className="flex items-center gap-2 flex-wrap">
        {status === 'online' && (
          <div className="flex items-center bg-raised border border-line-200 rounded-lg p-1 gap-1">
            <span className="text-[11px] font-mono text-ink-500 px-2 hidden sm:inline">
              Watchdog:
            </span>
            <button
              onClick={() => onExtendWatchdog?.(15)}
              disabled={isExtending}
              title="Extend auto-shutdown timeout by 15 minutes"
              className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-inset text-ink border border-line-200 hover:bg-strong hover:border-line-400 transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50"
            >
              <Plus className="w-3 h-3 text-verify" />
              <span>15m</span>
            </button>

            <button
              onClick={() => onExtendWatchdog?.(30)}
              disabled={isExtending}
              title="Extend auto-shutdown timeout by 30 minutes"
              className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-inset text-ink border border-line-200 hover:bg-strong hover:border-line-400 transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50"
            >
              <Plus className="w-3 h-3 text-verify" />
              <span>30m</span>
            </button>

            <button
              onClick={onResetWatchdog}
              disabled={isExtending}
              title="Reset watchdog timer back to default timeout"
              className="font-mono text-xs font-semibold px-2 py-1 rounded text-ink-700 hover:text-ink hover:bg-strong transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50"
            >
              <ShieldCheck className="w-3 h-3 text-ink-700" />
              <span className="hidden sm:inline">Reset</span>
            </button>
          </div>
        )}

        <button
          onClick={onRefresh}
          className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-line-200 bg-inset text-ink cursor-pointer inline-flex items-center gap-2 transition-all duration-150 hover:bg-strong hover:border-line-400 shrink-0"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh State</span>
        </button>
      </div>
    </div>
  );
}

