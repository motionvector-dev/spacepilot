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
      <div className="bg-surface border border-danger/30 rounded-3xl w-full max-w-lg p-6 shadow-lg flex flex-col gap-5 animate-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-danger-soft border border-danger/30">
              <AlertTriangle className="w-5 h-5 text-danger" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-danger">Terminate GPU Instance</h3>
              <p className="text-xs text-ink-700 mt-0.5">Destroy spot compute and immediately halt all billing.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-ink-500 hover:text-ink hover:bg-strong transition-all cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-ink-700 leading-relaxed">
          This will tear down the remote instance and destroy the local NVMe scratch volume. Final renders and synced checkpoints are preserved in your storage bucket.
        </p>

        <div className="bg-raised border border-line-200 rounded-xl p-4 flex flex-col gap-2 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-ink-500">Target Instance:</span>
            <span className="text-ink font-bold">{instanceId}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">Active Session Uptime:</span>
            <span className="text-ink">{uptimeText}</span>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-ink-700">
            Type <strong className="text-danger font-mono">TERMINATE</strong> to confirm destruction:
          </label>
          <input
            type="text"
            value={confirmInput}
            onChange={(e) => setConfirmInput(e.target.value)}
            placeholder="TERMINATE"
            autoFocus
            className="bg-raised border border-line-300 rounded-lg px-3 py-2 text-sm font-mono text-ink outline-none focus:border-danger transition-all"
          />
        </div>

        <div className="flex justify-end gap-2.5 pt-2">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="font-sans text-xs font-semibold px-4 py-2 rounded-lg border border-line-200 text-ink-700 hover:bg-inset transition-all cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!isConfirmed || isLoading}
            className="font-sans text-xs font-semibold px-5 py-2 rounded-lg bg-danger text-white hover:brightness-110 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Destroying Box...' : 'Destroy & Stop Billing'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
