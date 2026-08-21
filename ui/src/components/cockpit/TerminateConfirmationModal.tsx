import { useState } from 'react';
import { X, Trash2, AlertTriangle } from 'lucide-react';

interface TerminateConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  instanceId?: string;
  uptimeText?: string;
  isLoading?: boolean;
}

export function TerminateConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  instanceId = 'i-spot-active',
  uptimeText = '18m 42s',
  isLoading = false,
}: TerminateConfirmationModalProps) {
  const [confirmInput, setConfirmInput] = useState('');

  if (!isOpen) return null;

  const isConfirmed = confirmInput.trim().toUpperCase() === 'TERMINATE';

  const handleConfirm = () => {
    if (!isConfirmed) return;
    onConfirm();
    setConfirmInput('');
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#09090b] border border-[#f43535]/30 rounded-3xl w-full max-w-lg p-6 shadow-2xl flex flex-col gap-5 animate-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-[#f43535]/15 border border-[#f43535]/30">
              <AlertTriangle className="w-5 h-5 text-[#f43535]" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[#f43535]">Terminate GPU Instance</h3>
              <p className="text-xs text-[#a1a1aa] mt-0.5">Destroy spot compute and immediately halt all billing.</p>
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
          This will tear down the remote instance and destroy the local NVMe scratch volume. Final renders and synced checkpoints are preserved in your storage bucket.
        </p>

        <div className="bg-[#111114] border border-white/10 rounded-xl p-4 flex flex-col gap-2 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-[#71717a]">Target Instance:</span>
            <span className="text-[#fafafa] font-bold">{instanceId}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#71717a]">Active Session Uptime:</span>
            <span className="text-[#fafafa]">{uptimeText}</span>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-[#a1a1aa]">
            Type <strong className="text-[#f43535] font-mono">TERMINATE</strong> to confirm destruction:
          </label>
          <input
            type="text"
            value={confirmInput}
            onChange={(e) => setConfirmInput(e.target.value)}
            placeholder="TERMINATE"
            autoFocus
            className="bg-[#111114] border border-white/14 rounded-lg px-3 py-2 text-sm font-mono text-[#fafafa] outline-none focus:border-[#f43535] transition-all"
          />
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
            onClick={handleConfirm}
            disabled={!isConfirmed || isLoading}
            className="font-sans text-xs font-semibold px-5 py-2 rounded-lg bg-[#f43535] text-white hover:bg-[#e11d48] transition-all shadow-md flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Destroying Box...' : 'Destroy & Stop Billing'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
