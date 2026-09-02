import { X, Play, Zap, ShieldCheck } from 'lucide-react';

interface LaunchConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  instanceType?: string;
  region?: string;
  estimatedRate?: number;
  isLoading?: boolean;
}

export function LaunchConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  instanceType = 'g6e.xlarge',
  region = 'us-east-1',
  estimatedRate = 0.75,
  isLoading = false,
}: LaunchConfirmationModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-surface border border-line-300 rounded-3xl w-full max-w-lg p-6 shadow-lg flex flex-col gap-5 animate-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-raised border border-line-200">
              <Zap className="w-5 h-5 text-verify" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-ink">Confirm Spot GPU Launch</h3>
              <p className="text-xs text-ink-700 mt-0.5">Spin up AWS Spot compute &amp; warm resident VRAM.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-ink-500 hover:text-ink hover:bg-raised-hover transition-all cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-ink-700 leading-relaxed">
          You are about to launch an autonomous AWS EC2 Spot GPU instance. Spot billing will begin immediately upon allocation (~$0.75/hr vs $2.10/hr on-demand).
        </p>

        <div className="bg-raised border border-line-200 rounded-xl p-4 flex flex-col gap-2.5 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-ink-500">Instance Type:</span>
            <span className="text-ink font-bold">{instanceType} (L40S 48GB)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">AWS Target Region:</span>
            <span className="text-ink">{region}</span>
          </div>
          <div className="flex justify-between border-t border-line-200 pt-2">
            <span className="text-ink-500">Estimated Spot Rate:</span>
            <span className="text-verify font-bold">~${estimatedRate.toFixed(2)} / hr</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">Idle Guard Watchdog:</span>
            <span className="text-ink-900">20 min idle &mdash; will auto-terminate</span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-ink-500 bg-raised p-3 rounded-lg">
          <ShieldCheck className="w-4 h-4 text-verify shrink-0" />
          <span>Zero-Data-Loss enabled: Checkpoints and renders are synced continuously to R2 bucket.</span>
        </div>

        <div className="flex justify-end gap-2.5 pt-2">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="font-sans text-xs font-semibold px-4 py-2 rounded-lg border border-line-200 text-ink-700 hover:bg-raised-hover transition-all cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className="font-sans text-xs font-semibold px-5 py-2 rounded-lg bg-ink text-ground hover:brightness-110 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Launching Box...' : 'Confirm & Launch Spot GPU'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
