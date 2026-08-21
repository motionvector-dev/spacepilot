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
      <div className="bg-[#09090b] border border-white/14 rounded-3xl w-full max-w-lg p-6 shadow-2xl flex flex-col gap-5 animate-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-white/5 border border-white/10">
              <Zap className="w-5 h-5 text-[#10b981]" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[#fafafa]">Confirm Spot GPU Launch</h3>
              <p className="text-xs text-[#a1a1aa] mt-0.5">Spin up AWS Spot compute &amp; warm resident VRAM.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#71717a] hover:text-white hover:bg-white/10 transition-all cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-[#a1a1aa] leading-relaxed">
          You are about to launch an autonomous AWS EC2 Spot GPU instance. Spot billing will begin immediately upon allocation (~$0.75/hr vs $2.10/hr on-demand).
        </p>

        <div className="bg-[#111114] border border-white/10 rounded-xl p-4 flex flex-col gap-2.5 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-[#71717a]">Instance Type:</span>
            <span className="text-[#fafafa] font-bold">{instanceType} (L40S 48GB)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717a]">AWS Target Region:</span>
            <span className="text-[#fafafa]">{region}</span>
          </div>
          <div className="flex justify-between border-t border-white/5 pt-2">
            <span className="text-[#71717a]">Estimated Spot Rate:</span>
            <span className="text-[#10b981] font-bold">~${estimatedRate.toFixed(2)} / hr</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717a]">Idle Guard Watchdog:</span>
            <span className="text-[#f59e0b]">20 min Auto-Shutdown</span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-[#71717a] bg-white/5 p-3 rounded-lg">
          <ShieldCheck className="w-4 h-4 text-[#10b981] shrink-0" />
          <span>Zero-Data-Loss enabled: Checkpoints and renders are synced continuously to R2 bucket.</span>
        </div>

        <div className="flex justify-end gap-2.5 pt-2">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="font-sans text-xs font-semibold px-4 py-2 rounded-lg border border-white/10 text-[#a1a1aa] hover:bg-white/5 transition-all cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className="font-sans text-xs font-semibold px-5 py-2 rounded-lg bg-[#fafafa] text-[#09090b] hover:bg-white transition-all shadow-md flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Launching Box...' : 'Confirm & Launch Spot GPU'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
