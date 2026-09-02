import { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Volume2, 
  VolumeX, 
  Maximize2, 
  Sparkles, 
  Sliders, 
  FolderOpen,
  Eye,
  Grid
} from 'lucide-react';
import { useStudioStore } from '../../stores/studioStore';
import { useTimelineStore } from '../../stores/timelineStore';
import { secondsToSMPTE } from '../../lib/smpte';

declare global {
  interface Window {
    katex?: {
      render: (tex: string, element: HTMLElement, options?: Record<string, any>) => void;
    };
  }
}

export default function VibeCanvasView() {
  const { 
    takes,
    selectedTakeId,
    setSelectedTakeId
  } = useStudioStore();

  const { 
    currentTimeSeconds, 
    durationSeconds, 
    isPlaying, 
    togglePlay, 
    seek
  } = useTimelineStore();

  // Mathematical Overlay state
  const [cardTitle, setCardTitle] = useState('Diffusion Velocity Field');
  const [latexFormula, setLatexFormula] = useState('dx_t = f(x_t)dt + g(t)dw_t');
  const [accentColor, setAccentColor] = useState('#10b981');
  const [cardPos, setCardPos] = useState<'bottom_left' | 'center' | 'bottom_third'>('bottom_left');
  const [showOverlay, setShowOverlay] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  const katexRef = useRef<HTMLDivElement>(null);
  const inspectorKatexRef = useRef<HTMLDivElement>(null);

  // Dynamic KaTeX formula rendering
  useEffect(() => {
    if (window.katex) {
      if (katexRef.current) {
        try {
          window.katex.render(latexFormula, katexRef.current, { throwOnError: false, displayMode: true });
        } catch {}
      }
      if (inspectorKatexRef.current) {
        try {
          window.katex.render(latexFormula, inspectorKatexRef.current, { throwOnError: false, displayMode: true });
        } catch {}
      }
    }
  }, [latexFormula]);

  return (
    <div className="flex-1 grid grid-cols-12 overflow-hidden bg-ground font-sans select-none">
      {/* Left Column: Project Bin & Takes Shelf */}
      <aside className="col-span-12 lg:col-span-3 bg-surface border-r border-line-200 flex flex-col justify-between overflow-y-auto">
        <div className="p-4 flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-line-200">
            <span className="font-mono text-xs font-bold text-ink flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-verify" />
              Project Bin & Takes
            </span>
            <span className="font-mono text-[10px] text-ink-500 bg-inset px-2 py-0.5 rounded border border-line-200">
              {takes.length} Takes
            </span>
          </div>

          {/* Takes Scroller */}
          <div className="flex flex-col gap-2">
            {takes.map((take) => (
              <div
                key={take.id}
                onClick={() => setSelectedTakeId(take.id)}
                className={`p-3 rounded-xl border cursor-pointer transition-all flex flex-col gap-1.5 ${
                  selectedTakeId === take.id
                    ? 'bg-inset border-verify'
                    : 'bg-raised border-line-200 hover:border-line-300'
                }`}
              >
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="font-bold text-ink">Take #{take.id}</span>
                  <span className="text-verify font-bold text-[10px]">SEED {take.seed}</span>
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono text-ink-500">
                  <span>Pan: +{take.panDeg}°</span>
                  <span>Zoom: {take.zoomRatio}x</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Spot GPU Daemon VRAM Status */}
        <div className="p-4 border-t border-line-200 bg-raised">
          <div className="flex justify-between items-center text-xs font-mono text-ink-700 mb-2">
            <span>Daemon VRAM</span>
            <span className="text-verify font-bold">18.4 / 48 GB</span>
          </div>
          <div className="h-1.5 bg-ground rounded-full overflow-hidden border border-line-200">
            <div className="h-full bg-verify w-[38%]" />
          </div>
        </div>
      </aside>

      {/* Center Column: Cinema Viewport & Scrubber */}
      <main className="col-span-12 lg:col-span-6 bg-ground flex flex-col justify-between overflow-hidden relative border-r border-line-200">
        {/* Viewport Top Bar */}
        <div className="h-10 bg-surface/80 backdrop-blur border-b border-line-200 px-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-verify animate-pulse" />
            <span className="font-mono text-xs font-bold text-ink">
              LTX-2.5 CINEMA VIEWPORT
            </span>
          </div>

          <div className="flex items-center gap-2 font-mono text-[10px]">
            <button
              onClick={() => setShowOverlay(!showOverlay)}
              className={`px-2.5 py-0.5 rounded border transition-all cursor-pointer flex items-center gap-1 ${
                showOverlay ? 'bg-strong text-ink border-line-400' : 'text-ink-500 border-transparent hover:text-ink'
              }`}
            >
              <Eye className="w-3 h-3 text-ink-700" />
              <span>Math Card</span>
            </button>
            <button
              onClick={() => setShowGrid(!showGrid)}
              className={`px-2.5 py-0.5 rounded border transition-all cursor-pointer flex items-center gap-1 ${
                showGrid ? 'bg-strong text-ink border-line-400' : 'text-ink-500 border-transparent hover:text-ink'
              }`}
            >
              <Grid className="w-3 h-3 text-ink-700" />
              <span>Grid</span>
            </button>
          </div>
        </div>

        {/* Viewport Canvas Container */}
        <div className="flex-1 flex items-center justify-center p-6 relative overflow-hidden">
          <div className="w-full aspect-video bg-surface border border-line-200 rounded-2xl relative overflow-hidden flex flex-col justify-between p-4">
            {/* Resolution Tag */}
            <div className="z-10 flex justify-between items-center">
              <span className="font-mono text-[10px] text-ink bg-ground/80 px-2.5 py-1 rounded border border-line-200">
                1920×1080 @ 24fps · ProRes 422
              </span>
              <span className="font-mono text-[10px] text-verify bg-verify-soft px-2.5 py-1 rounded border border-verify/30 font-bold">
                P0 COMPOSITE ORDER
              </span>
            </div>

            {/* Draggable Glassmorphic LaTeX Mathematical Card Overlay */}
            {showOverlay && (
              <div
                className={`z-20 transition-all ${
                  cardPos === 'bottom_left'
                    ? 'self-start mt-auto'
                    : cardPos === 'center'
                    ? 'self-center my-auto'
                    : 'self-center mt-auto mb-4'
                }`}
              >
                <div className="bg-raised/90 backdrop-blur-xl border border-line-300 p-3.5 rounded-xl shadow-lg min-w-[260px] flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-3.5 rounded-full" style={{ backgroundColor: accentColor }} />
                      <span className="text-xs font-bold text-ink font-sans">{cardTitle}</span>
                    </div>
                    <span className="font-mono text-[9px] text-ink-500 bg-inset px-1.5 py-0.5 rounded">
                      VELLO 4K
                    </span>
                  </div>

                  <div ref={katexRef} className="text-ink text-xs font-mono my-1 min-h-[24px]">
                    {latexFormula}
                  </div>

                  <div className="text-[9px] font-mono text-ink-500 flex justify-between border-t border-line-200 pt-1">
                    <span>MotionVector Native</span>
                    <span>t = {currentTimeSeconds.toFixed(2)}s</span>
                  </div>
                </div>
              </div>
            )}

            {/* Center Play Button Overlay */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <button
                onClick={togglePlay}
                className="w-14 h-14 rounded-full bg-inset hover:bg-strong border border-line-300 flex items-center justify-center backdrop-blur-md pointer-events-auto transition-all cursor-pointer"
              >
                {isPlaying ? (
                  <Pause className="w-6 h-6 fill-ink text-ink" />
                ) : (
                  <Play className="w-6 h-6 fill-ink text-ink ml-1" />
                )}
              </button>
            </div>

            {/* Safe Margins Guide */}
            {showGrid && (
              <div className="absolute inset-4 border border-line-300 pointer-events-none rounded-xl flex items-center justify-center">
                <div className="w-4 h-4 border-t border-l border-line-400 absolute top-0 left-0" />
                <div className="w-4 h-4 border-t border-r border-line-400 absolute top-0 right-0" />
                <div className="w-4 h-4 border-b border-l border-line-400 absolute bottom-0 left-0" />
                <div className="w-4 h-4 border-b border-r border-line-400 absolute bottom-0 right-0" />
                <div className="w-full h-px bg-line-200" />
                <div className="h-full w-px bg-line-200 absolute" />
              </div>
            )}
          </div>
        </div>

        {/* Viewport Scrubber & Floating Transport */}
        <div className="bg-surface border-t border-line-200 p-3 flex flex-col gap-2">
          {/* Progress Bar Track */}
          <div
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pos = (e.clientX - rect.left) / rect.width;
              seek(pos * durationSeconds);
            }}
            className="h-2 bg-inset rounded-full cursor-pointer relative overflow-hidden group"
          >
            <div
              className="h-full bg-verify transition-all duration-75"
              style={{ width: `${(currentTimeSeconds / durationSeconds) * 100}%` }}
            />
          </div>

          {/* Transport Controls */}
          <div className="flex items-center justify-between font-mono text-xs text-ink">
            <div className="flex items-center gap-2">
              <button
                onClick={togglePlay}
                className="p-1.5 rounded hover:bg-inset cursor-pointer"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
              <button
                onClick={() => seek(0)}
                className="p-1.5 rounded hover:bg-inset cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <div className="h-4 w-px bg-line-200 mx-1" />
              <span className="text-verify font-bold">{secondsToSMPTE(currentTimeSeconds)}</span>
              <span className="text-ink-500">/ {secondsToSMPTE(durationSeconds)}</span>
            </div>

            <div className="flex items-center gap-3 text-ink-700">
              <button
                onClick={() => setIsMuted(!isMuted)}
                className="hover:text-ink cursor-pointer"
              >
                {isMuted ? <VolumeX className="w-4 h-4 text-danger" /> : <Volume2 className="w-4 h-4" />}
              </button>
              <button className="hover:text-ink cursor-pointer">
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Right Column: MotionVector & LaTeX Inspector */}
      <aside className="col-span-12 lg:col-span-3 bg-surface flex flex-col justify-between p-5 overflow-y-auto">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-line-200">
            <span className="font-mono text-xs font-bold text-ink flex items-center gap-2">
              <Sliders className="w-4 h-4 text-ink-700" />
              MotionVector Inspector
            </span>
            <span className="font-mono text-[10px] text-ink bg-inset border border-line-300 px-1.5 py-0.5 rounded">
              VELLO NATIVE
            </span>
          </div>

          {/* Card Title Input */}
          <div>
            <label className="font-mono text-[10px] font-bold text-ink-500 uppercase block mb-1.5">
              Vector Card Title
            </label>
            <input
              type="text"
              value={cardTitle}
              onChange={(e) => setCardTitle(e.target.value)}
              className="w-full bg-raised border border-line-200 rounded-lg px-3 py-1.5 text-xs text-ink focus:outline-none focus:border-verify"
            />
          </div>

          {/* LaTeX Formula Editor */}
          <div>
            <label className="font-mono text-[10px] font-bold text-ink-500 uppercase block mb-1.5">
              LaTeX Math Formula
            </label>
            <textarea
              value={latexFormula}
              onChange={(e) => setLatexFormula(e.target.value)}
              rows={2}
              className="w-full bg-raised border border-line-200 rounded-lg p-2.5 text-xs font-mono text-ink focus:outline-none focus:border-verify resize-none"
            />
          </div>

          {/* Live KaTeX Inspector Preview */}
          <div className="bg-raised p-3 rounded-xl border border-line-200">
            <span className="font-mono text-[9px] text-ink-500 block mb-1">
              Live Inspector KaTeX Preview:
            </span>
            <div ref={inspectorKatexRef} className="text-ink text-xs font-mono min-h-[20px]">
              {latexFormula}
            </div>
          </div>

          {/* Accent Color Picker — the swatch colors are user-facing overlay-card data, not chrome, so they are left as-is */}
          <div>
            <label className="font-mono text-[10px] font-bold text-ink-500 uppercase block mb-1.5">
              Accent Color
            </label>
            <div className="flex items-center gap-2">
              {['#10b981', '#06b6d4', '#a855f7', '#f59e0b', '#fafafa'].map((color) => (
                <button
                  key={color}
                  onClick={() => setAccentColor(color)}
                  className={`w-6 h-6 rounded-full border-2 transition-all cursor-pointer ${
                    accentColor === color ? 'border-ink scale-110' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>

          {/* Position Anchor */}
          <div>
            <label className="font-mono text-[10px] font-bold text-ink-500 uppercase block mb-1.5">
              Position Anchor
            </label>
            <div className="grid grid-cols-3 gap-1.5 font-mono text-[10px]">
              <button
                onClick={() => setCardPos('bottom_left')}
                className={`py-1.5 rounded-lg border transition-all cursor-pointer ${
                  cardPos === 'bottom_left'
                    ? 'bg-inset text-ink border-verify font-bold'
                    : 'bg-raised text-ink-500 border-line-200'
                }`}
              >
                Bottom Left
              </button>
              <button
                onClick={() => setCardPos('center')}
                className={`py-1.5 rounded-lg border transition-all cursor-pointer ${
                  cardPos === 'center'
                    ? 'bg-inset text-ink border-verify font-bold'
                    : 'bg-raised text-ink-500 border-line-200'
                }`}
              >
                Center
              </button>
              <button
                onClick={() => setCardPos('bottom_third')}
                className={`py-1.5 rounded-lg border transition-all cursor-pointer ${
                  cardPos === 'bottom_third'
                    ? 'bg-inset text-ink border-verify font-bold'
                    : 'bg-raised text-ink-500 border-line-200'
                }`}
              >
                Lower Third
              </button>
            </div>
          </div>
        </div>

        {/* 4K Vello Composite Action */}
        <button className="w-full bg-accent hover:brightness-110 text-accent-contrast font-extrabold text-xs py-3 rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer mt-4">
          <Sparkles className="w-3.5 h-3.5" />
          Export 4K Master (Vello Composite)
        </button>
      </aside>
    </div>
  );
}
