import { useState } from 'react';
import { 
  Download, 
  X, 
  Sparkles, 
  Sliders, 
  Layers
} from 'lucide-react';
import { useStudioStore } from '../../stores/studioStore';
import { telemetry } from '../../lib/telemetry';

export default function ExportDrawer({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [resolution, setResolution] = useState<'4k' | '1080p' | '720p'>('4k');
  const [codec, setCodec] = useState<'prores422' | 'h264' | 'h265'>('prores422');
  const [compositeVello, setCompositeVello] = useState(true);
  const [loudnormAudio, setLoudnormAudio] = useState(true);
  const [isExporting, setIsExporting] = useState(false);

  const { scenes, activeMode } = useStudioStore();

  if (!isOpen) return null;

  const handleExport = () => {
    setIsExporting(true);
    telemetry.trackClick('dispatch_export_master', { resolution, codec, compositeVello });

    setTimeout(() => {
      setIsExporting(false);
      alert(`Master Export dispatched: ProRes 422 HQ 3840×2160 UHD with P0 Vello Composite.`);
      onClose();
    }, 1500);
  };

  return (
    <div 
      onClick={onClose}
      className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-end font-sans"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md h-full bg-surface border-l border-line-200 shadow-lg flex flex-col justify-between p-6 overflow-y-auto animate-in slide-in-from-right duration-200"
      >
        <div className="flex flex-col gap-6">
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-line-200">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-5 h-5 text-verify" />
              <h2 className="text-sm font-extrabold text-ink uppercase tracking-wider">
                Export Master Delivery
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-inset text-ink-500 hover:text-ink cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Delivery Preset Matrix */}
          <div className="flex flex-col gap-4">
            <span className="font-mono text-xs font-bold text-ink-700 uppercase tracking-wider">
              Output Format & Resolution
            </span>

            {/* Resolution Buttons */}
            <div className="grid grid-cols-3 gap-2 font-mono text-xs">
              <button
                onClick={() => setResolution('4k')}
                className={`p-3 rounded-lg border flex flex-col items-center gap-1 transition-all cursor-pointer ${
                  resolution === '4k'
                    ? 'bg-inset border-verify text-ink font-bold ring-1 ring-verify'
                    : 'bg-raised border-line-200 text-ink-500'
                }`}
              >
                <span>3840×2160</span>
                <span className="text-[10px] text-verify">4K UHD</span>
              </button>

              <button
                onClick={() => setResolution('1080p')}
                className={`p-3 rounded-lg border flex flex-col items-center gap-1 transition-all cursor-pointer ${
                  resolution === '1080p'
                    ? 'bg-inset border-verify text-ink font-bold ring-1 ring-verify'
                    : 'bg-raised border-line-200 text-ink-500'
                }`}
              >
                <span>1920×1080</span>
                <span className="text-[10px] text-ink-500">FHD</span>
              </button>

              <button
                onClick={() => setResolution('720p')}
                className={`p-3 rounded-lg border flex flex-col items-center gap-1 transition-all cursor-pointer ${
                  resolution === '720p'
                    ? 'bg-inset border-verify text-ink font-bold ring-1 ring-verify'
                    : 'bg-raised border-line-200 text-ink-500'
                }`}
              >
                <span>1280×720</span>
                <span className="text-[10px] text-ink-500">Preview</span>
              </button>
            </div>

            {/* Codec Preset */}
            <div className="flex flex-col gap-2">
              <label className="font-mono text-[10px] font-bold text-ink-500 uppercase">
                Video Codec Container
              </label>
              <div className="grid grid-cols-3 gap-2 font-mono text-xs">
                {(['prores422', 'h264', 'h265'] as const).map((c) => (
                  <button
                    key={c}
                    onClick={() => setCodec(c)}
                    className={`py-2 rounded border uppercase text-center transition-all cursor-pointer ${
                      codec === c
                        ? 'bg-inset border-ink text-ink font-bold'
                        : 'bg-raised border-line-200 text-ink-500'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {/* P0 Composite Toggles */}
            <div className="bg-raised p-4 rounded-xl border border-line-200 flex flex-col gap-3 font-mono text-xs">
              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-ink flex items-center gap-2">
                  <Layers className="w-3.5 h-3.5 text-verify" />
                  P0 Vello 4K Vector Composite
                </span>
                <input
                  type="checkbox"
                  checked={compositeVello}
                  onChange={(e) => setCompositeVello(e.target.checked)}
                  className="accent-verify w-4 h-4"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-ink flex items-center gap-2">
                  <Sliders className="w-3.5 h-3.5 text-ink-900" />
                  -16.0 LUFS EBU R128 Loudnorm
                </span>
                <input
                  type="checkbox"
                  checked={loudnormAudio}
                  onChange={(e) => setLoudnormAudio(e.target.checked)}
                  className="accent-ink-900 w-4 h-4"
                />
              </label>
            </div>

            {/* Summary Box */}
            <div className="bg-inset p-3 rounded-lg border border-line-200 font-mono text-xs text-ink-700 flex flex-col gap-1">
              <div className="flex justify-between">
                <span>Scope:</span>
                <span className="text-ink font-bold">
                  {activeMode === 'director' ? `${scenes.length} Scenes Reel` : 'Current Shot Take'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Estimated Size:</span>
                <span className="text-ink font-bold">~420 MB</span>
              </div>
              <div className="flex justify-between">
                <span>Target Pipeline:</span>
                <span className="text-verify font-bold">Remote L40S Spot</span>
              </div>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="w-full bg-accent hover:brightness-110 text-accent-contrast font-extrabold text-sm py-3.5 rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 mt-6"
        >
          <Download className="w-4 h-4" />
          <span>{isExporting ? 'Packaging Master...' : 'Start Export Master'}</span>
        </button>
      </div>
    </div>
  );
}
