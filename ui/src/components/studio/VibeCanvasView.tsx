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
    <div className="flex-1 grid grid-cols-12 overflow-hidden bg-black font-sans select-none">
      {/* Left Column: Project Bin & Takes Shelf */}
      <aside className="col-span-12 lg:col-span-3 bg-[#09090b] border-r border-white/10 flex flex-col justify-between overflow-y-auto">
        <div className="p-4 flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <span className="font-mono text-xs font-bold text-white flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-emerald-400" />
              Project Bin & Takes
            </span>
            <span className="font-mono text-[10px] text-white/50 bg-white/5 px-2 py-0.5 rounded border border-white/10">
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
                    ? 'bg-[#18181b] border-emerald-400 shadow-[0_0_16px_rgba(16,185,129,0.2)]'
                    : 'bg-[#111114] border-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="font-bold text-white">Take #{take.id}</span>
                  <span className="text-emerald-400 font-bold text-[10px]">SEED {take.seed}</span>
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono text-white/50">
                  <span>Pan: +{take.panDeg}°</span>
                  <span>Zoom: {take.zoomRatio}x</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Spot GPU Daemon VRAM Status */}
        <div className="p-4 border-t border-white/10 bg-[#111114]">
          <div className="flex justify-between items-center text-xs font-mono text-white/70 mb-2">
            <span>Daemon VRAM</span>
            <span className="text-emerald-400 font-bold">18.4 / 48 GB</span>
          </div>
          <div className="h-1.5 bg-black rounded-full overflow-hidden border border-white/10">
            <div className="h-full bg-emerald-400 w-[38%]" />
          </div>
        </div>
      </aside>

      {/* Center Column: Cinema Viewport & Scrubber */}
      <main className="col-span-12 lg:col-span-6 bg-black flex flex-col justify-between overflow-hidden relative border-r border-white/10">
        {/* Viewport Top Bar */}
        <div className="h-10 bg-[#09090b]/80 backdrop-blur border-b border-white/10 px-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-mono text-xs font-bold text-white">
              LTX-2.5 CINEMA VIEWPORT
            </span>
          </div>

          <div className="flex items-center gap-2 font-mono text-[10px]">
            <button
              onClick={() => setShowOverlay(!showOverlay)}
              className={`px-2.5 py-0.5 rounded border transition-all cursor-pointer flex items-center gap-1 ${
                showOverlay ? 'bg-white/15 text-white border-white/30' : 'text-white/40 border-transparent hover:text-white'
              }`}
            >
              <Eye className="w-3 h-3 text-cyan-400" />
              <span>Math Card</span>
            </button>
            <button
              onClick={() => setShowGrid(!showGrid)}
              className={`px-2.5 py-0.5 rounded border transition-all cursor-pointer flex items-center gap-1 ${
                showGrid ? 'bg-white/15 text-white border-white/30' : 'text-white/40 border-transparent hover:text-white'
              }`}
            >
              <Grid className="w-3 h-3 text-purple-400" />
              <span>Grid</span>
            </button>
          </div>
        </div>

        {/* Viewport Canvas Container */}
        <div className="flex-1 flex items-center justify-center p-6 relative overflow-hidden">
          <div className="w-full aspect-video bg-[#09090b] border border-white/10 rounded-2xl relative overflow-hidden shadow-2xl flex flex-col justify-between p-4">
            {/* Resolution Tag */}
            <div className="z-10 flex justify-between items-center">
              <span className="font-mono text-[10px] text-white bg-black/80 px-2.5 py-1 rounded border border-white/10">
                1920×1080 @ 24fps · ProRes 422
              </span>
              <span className="font-mono text-[10px] text-emerald-400 bg-emerald-500/15 px-2.5 py-1 rounded border border-emerald-500/30 font-bold">
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
                <div className="bg-[#111114]/90 backdrop-blur-xl border border-white/20 p-3.5 rounded-xl shadow-2xl min-w-[260px] flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-3.5 rounded-full" style={{ backgroundColor: accentColor }} />
                      <span className="text-xs font-bold text-white font-sans">{cardTitle}</span>
                    </div>
                    <span className="font-mono text-[9px] text-white/50 bg-white/10 px-1.5 py-0.5 rounded">
                      VELLO 4K
                    </span>
                  </div>

                  <div ref={katexRef} className="text-white text-xs font-mono my-1 min-h-[24px]">
                    {latexFormula}
                  </div>

                  <div className="text-[9px] font-mono text-white/40 flex justify-between border-t border-white/10 pt-1">
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
                className="w-14 h-14 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 flex items-center justify-center backdrop-blur-md pointer-events-auto transition-all cursor-pointer"
              >
                {isPlaying ? (
                  <Pause className="w-6 h-6 fill-white text-white" />
                ) : (
                  <Play className="w-6 h-6 fill-white text-white ml-1" />
                )}
              </button>
            </div>

            {/* Safe Margins Guide */}
            {showGrid && (
              <div className="absolute inset-4 border border-cyan-400/30 pointer-events-none rounded-xl flex items-center justify-center">
                <div className="w-4 h-4 border-t border-l border-cyan-400/60 absolute top-0 left-0" />
                <div className="w-4 h-4 border-t border-r border-cyan-400/60 absolute top-0 right-0" />
                <div className="w-4 h-4 border-b border-l border-cyan-400/60 absolute bottom-0 left-0" />
                <div className="w-4 h-4 border-b border-r border-cyan-400/60 absolute bottom-0 right-0" />
                <div className="w-full h-px bg-cyan-400/20" />
                <div className="h-full w-px bg-cyan-400/20 absolute" />
              </div>
            )}
          </div>
        </div>

        {/* Viewport Scrubber & Floating Transport */}
        <div className="bg-[#09090b] border-t border-white/10 p-3 flex flex-col gap-2">
          {/* Progress Bar Track */}
          <div
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pos = (e.clientX - rect.left) / rect.width;
              seek(pos * durationSeconds);
            }}
            className="h-2 bg-[#18181b] rounded-full cursor-pointer relative overflow-hidden group"
          >
            <div
              className="h-full bg-emerald-400 transition-all duration-75"
              style={{ width: `${(currentTimeSeconds / durationSeconds) * 100}%` }}
            />
          </div>

          {/* Transport Controls */}
          <div className="flex items-center justify-between font-mono text-xs text-white">
            <div className="flex items-center gap-2">
              <button
                onClick={togglePlay}
                className="p-1.5 rounded hover:bg-white/10 cursor-pointer"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
              <button
                onClick={() => seek(0)}
                className="p-1.5 rounded hover:bg-white/10 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <div className="h-4 w-px bg-white/10 mx-1" />
              <span className="text-emerald-400 font-bold">{secondsToSMPTE(currentTimeSeconds)}</span>
              <span className="text-white/40">/ {secondsToSMPTE(durationSeconds)}</span>
            </div>

            <div className="flex items-center gap-3 text-white/60">
              <button
                onClick={() => setIsMuted(!isMuted)}
                className="hover:text-white cursor-pointer"
              >
                {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
              </button>
              <button className="hover:text-white cursor-pointer">
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Right Column: MotionVector & LaTeX Inspector */}
      <aside className="col-span-12 lg:col-span-3 bg-[#09090b] flex flex-col justify-between p-5 overflow-y-auto">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <span className="font-mono text-xs font-bold text-white flex items-center gap-2">
              <Sliders className="w-4 h-4 text-cyan-400" />
              MotionVector Inspector
            </span>
            <span className="font-mono text-[10px] text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 px-1.5 py-0.5 rounded">
              VELLO NATIVE
            </span>
          </div>

          {/* Card Title Input */}
          <div>
            <label className="font-mono text-[10px] font-bold text-white/50 uppercase block mb-1.5">
              Vector Card Title
            </label>
            <input
              type="text"
              value={cardTitle}
              onChange={(e) => setCardTitle(e.target.value)}
              className="w-full bg-[#111114] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-400"
            />
          </div>

          {/* LaTeX Formula Editor */}
          <div>
            <label className="font-mono text-[10px] font-bold text-white/50 uppercase block mb-1.5">
              LaTeX Math Formula
            </label>
            <textarea
              value={latexFormula}
              onChange={(e) => setLatexFormula(e.target.value)}
              rows={2}
              className="w-full bg-[#111114] border border-white/10 rounded-lg p-2.5 text-xs font-mono text-white focus:outline-none focus:border-emerald-400 resize-none"
            />
          </div>

          {/* Live KaTeX Inspector Preview */}
          <div className="bg-[#111114] p-3 rounded-xl border border-white/10">
            <span className="font-mono text-[9px] text-white/40 block mb-1">
              Live Inspector KaTeX Preview:
            </span>
            <div ref={inspectorKatexRef} className="text-white text-xs font-mono min-h-[20px]">
              {latexFormula}
            </div>
          </div>

          {/* Accent Color Picker */}
          <div>
            <label className="font-mono text-[10px] font-bold text-white/50 uppercase block mb-1.5">
              Accent Color
            </label>
            <div className="flex items-center gap-2">
              {['#10b981', '#06b6d4', '#a855f7', '#f59e0b', '#fafafa'].map((color) => (
                <button
                  key={color}
                  onClick={() => setAccentColor(color)}
                  className={`w-6 h-6 rounded-full border-2 transition-all cursor-pointer ${
                    accentColor === color ? 'border-white scale-110' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>

          {/* Position Anchor */}
          <div>
            <label className="font-mono text-[10px] font-bold text-white/50 uppercase block mb-1.5">
              Position Anchor
            </label>
            <div className="grid grid-cols-3 gap-1.5 font-mono text-[10px]">
              <button
                onClick={() => setCardPos('bottom_left')}
                className={`py-1.5 rounded-lg border transition-all cursor-pointer ${
                  cardPos === 'bottom_left'
                    ? 'bg-[#18181b] text-white border-emerald-400 font-bold'
                    : 'bg-[#111114] text-white/50 border-white/10'
                }`}
              >
                Bottom Left
              </button>
              <button
                onClick={() => setCardPos('center')}
                className={`py-1.5 rounded-lg border transition-all cursor-pointer ${
                  cardPos === 'center'
                    ? 'bg-[#18181b] text-white border-emerald-400 font-bold'
                    : 'bg-[#111114] text-white/50 border-white/10'
                }`}
              >
                Center
              </button>
              <button
                onClick={() => setCardPos('bottom_third')}
                className={`py-1.5 rounded-lg border transition-all cursor-pointer ${
                  cardPos === 'bottom_third'
                    ? 'bg-[#18181b] text-white border-emerald-400 font-bold'
                    : 'bg-[#111114] text-white/50 border-white/10'
                }`}
              >
                Lower Third
              </button>
            </div>
          </div>
        </div>

        {/* 4K Vello Composite Action */}
        <button className="w-full bg-white hover:bg-zinc-200 text-black font-extrabold text-xs py-3 rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_16px_rgba(255,255,255,0.15)] mt-4">
          <Sparkles className="w-3.5 h-3.5" />
          Export 4K Master (Vello Composite)
        </button>
      </aside>
    </div>
  );
}
