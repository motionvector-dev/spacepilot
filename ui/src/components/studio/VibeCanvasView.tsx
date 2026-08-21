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
  FolderOpen
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

  const { currentTimeSeconds, durationSeconds, isPlaying, setIsPlaying, setCurrentTime } = useTimelineStore();

  // Overlay state
  const [cardTitle, setCardTitle] = useState('Diffusion Velocity Field');
  const [latexFormula, setLatexFormula] = useState('dx_t = f(x_t)dt + g(t)dw_t');
  const [accentColor, setAccentColor] = useState('#10b981');
  const [cardPos, setCardPos] = useState<'bottom_left' | 'center' | 'bottom_third'>('bottom_left');
  const [showOverlay, setShowOverlay] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  const katexRef = useRef<HTMLDivElement>(null);
  const inspectorKatexRef = useRef<HTMLDivElement>(null);

  // Re-render KaTeX formula dynamically
  useEffect(() => {
    if (window.katex) {
      if (katexRef.current) {
        try {
          window.katex.render(latexFormula, katexRef.current, { throwOnError: false, displayMode: true });
        } catch (e) {}
      }
      if (inspectorKatexRef.current) {
        try {
          window.katex.render(latexFormula, inspectorKatexRef.current, { throwOnError: false, displayMode: true });
        } catch (e) {}
      }
    }
  }, [latexFormula]);

  return (
    <div className="flex-1 grid grid-cols-12 overflow-hidden bg-black font-sans">
      {/* Left Column: Project Bin & Takes Shelf */}
      <aside className="col-span-12 lg:col-span-3 bg-[#09090b] border-r border-white/[0.08] flex flex-col justify-between overflow-y-auto">
        <div className="p-4 flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <span className="font-mono text-xs font-bold text-white flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-[#10b981]" />
              Project Bin & Takes
            </span>
            <span className="font-mono text-[10px] text-[#71717a] bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.08]">
              {takes.length} Takes
            </span>
          </div>

          {/* Takes Scroller */}
          <div className="flex flex-col gap-2.5">
            {takes.map((take) => (
              <div
                key={take.id}
                onClick={() => setSelectedTakeId(take.id)}
                className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col gap-1.5 ${
                  selectedTakeId === take.id
                    ? 'bg-[#18181b] border-[#10b981] shadow-[0_0_16px_rgba(16,185,129,0.2)]'
                    : 'bg-[#111114] border-white/[0.08] hover:border-white/[0.2]'
                }`}
              >
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="font-bold text-white">Take #{take.id}</span>
                  <span className="text-[#10b981] font-bold text-[10px]">SEED {take.seed}</span>
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono text-[#71717a]">
                  <span>Pan: +{take.panDeg}°</span>
                  <span>Zoom: {take.zoomRatio}x</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Spot GPU Quick Launch Bar */}
        <div className="p-4 border-t border-white/[0.08] bg-[#111114]">
          <div className="flex justify-between items-center text-xs font-mono text-[#a1a1aa] mb-2">
            <span>Daemon VRAM</span>
            <span className="text-[#10b981] font-bold">18.4 / 48 GB</span>
          </div>
          <div className="h-1.5 bg-black rounded-full overflow-hidden border border-white/[0.08]">
            <div className="h-full bg-[#10b981] w-[38%]" />
          </div>
        </div>
      </aside>

      {/* Center Column: Cinema Viewport & Scrubber */}
      <main className="col-span-12 lg:col-span-6 bg-black flex flex-col justify-between overflow-hidden relative border-r border-white/[0.08]">
        {/* Viewport Top Bar */}
        <div className="h-10 bg-[#09090b]/80 backdrop-blur border-b border-white/[0.08] px-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#10b981]" />
            <span className="font-mono text-xs font-bold text-white">
              LTX-2.5 CINEMA VIEWPORT
            </span>
          </div>

          <div className="flex items-center gap-2 font-mono text-[10px]">
            <button
              onClick={() => setShowOverlay(!showOverlay)}
              className={`px-2 py-0.5 rounded border transition-all cursor-pointer ${
                showOverlay ? 'bg-white/10 text-white border-white/20' : 'text-[#71717a] border-transparent'
              }`}
            >
              Math Card
            </button>
            <button
              onClick={() => setShowGrid(!showGrid)}
              className={`px-2 py-0.5 rounded border transition-all cursor-pointer ${
                showGrid ? 'bg-white/10 text-white border-white/20' : 'text-[#71717a] border-transparent'
              }`}
            >
              Grid
            </button>
          </div>
        </div>

        {/* Viewport Canvas Container */}
        <div className="flex-1 flex items-center justify-center p-6 relative overflow-hidden">
          <div className="w-full aspect-video bg-[#09090b] border border-white/[0.1] rounded-xl relative overflow-hidden shadow-2xl flex flex-col justify-between p-4">
            {/* Resolution Tag */}
            <div className="z-10 flex justify-between items-center">
              <span className="font-mono text-[10px] text-white bg-black/80 px-2 py-0.5 rounded border border-white/[0.08]">
                1920×1080 @ 24fps · ProRes 422
              </span>
              <span className="font-mono text-[10px] text-[#10b981] bg-[#10b981]/15 px-2 py-0.5 rounded border border-[#10b981]/30 font-bold">
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
                <div className="bg-[#111114]/90 backdrop-blur-xl border border-white/[0.15] p-3.5 rounded-xl shadow-2xl min-w-[260px] flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-3.5 rounded-full" style={{ backgroundColor: accentColor }} />
                      <span className="text-xs font-bold text-white font-sans">{cardTitle}</span>
                    </div>
                    <span className="font-mono text-[9px] text-[#71717a] bg-white/[0.06] px-1.5 py-0.5 rounded">
                      VELLO 4K
                    </span>
                  </div>

                  <div ref={katexRef} className="text-white text-xs font-mono my-1 min-h-[24px]" />

                  <div className="text-[9px] font-mono text-[#71717a] flex justify-between border-t border-white/[0.06] pt-1">
                    <span>MotionVector Native</span>
                    <span>t = {(currentTimeSeconds).toFixed(2)}s</span>
                  </div>
                </div>
              </div>
            )}

            {/* Center Play Button Overlay */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
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
              <div className="absolute inset-4 border border-[#38bdf8]/30 pointer-events-none rounded flex items-center justify-center">
                <div className="w-4 h-4 border-t border-l border-[#38bdf8]/60 absolute top-0 left-0" />
                <div className="w-4 h-4 border-t border-r border-[#38bdf8]/60 absolute top-0 right-0" />
                <div className="w-4 h-4 border-b border-l border-[#38bdf8]/60 absolute bottom-0 left-0" />
                <div className="w-4 h-4 border-b border-r border-[#38bdf8]/60 absolute bottom-0 right-0" />
                <div className="w-full h-px bg-[#38bdf8]/20" />
                <div className="h-full w-px bg-[#38bdf8]/20 absolute" />
              </div>
            )}
          </div>
        </div>

        {/* Viewport Scrubber & Floating Transport */}
        <div className="bg-[#09090b] border-t border-white/[0.08] p-3 flex flex-col gap-2">
          {/* Progress Bar Track */}
          <div
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pos = (e.clientX - rect.left) / rect.width;
              setCurrentTime(pos * durationSeconds);
            }}
            className="h-2 bg-[#18181b] rounded-full cursor-pointer relative overflow-hidden group"
          >
            <div
              className="h-full bg-[#10b981] transition-all"
              style={{ width: `${(currentTimeSeconds / durationSeconds) * 100}%` }}
            />
          </div>

          {/* Transport Controls */}
          <div className="flex items-center justify-between font-mono text-xs text-white">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="p-1.5 rounded hover:bg-white/[0.08] cursor-pointer"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
              <button
                onClick={() => setCurrentTime(0)}
                className="p-1.5 rounded hover:bg-white/[0.08] cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <div className="h-4 w-px bg-white/[0.1] mx-1" />
              <span className="text-[#10b981] font-bold">{secondsToSMPTE(currentTimeSeconds)}</span>
              <span className="text-[#71717a]">/ {secondsToSMPTE(durationSeconds)}</span>
            </div>

            <div className="flex items-center gap-3 text-[#a1a1aa]">
              <button
                onClick={() => setIsMuted(!isMuted)}
                className="hover:text-white cursor-pointer"
              >
                {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
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
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <span className="font-mono text-xs font-bold text-white flex items-center gap-2">
              <Sliders className="w-4 h-4 text-[#06b6d4]" />
              MotionVector Inspector
            </span>
            <span className="font-mono text-[10px] text-[#06b6d4] bg-[#06b6d4]/10 border border-[#06b6d4]/30 px-1.5 py-0.5 rounded">
              VELLO NATIVE
            </span>
          </div>

          {/* Card Title Input */}
          <div>
            <label className="font-mono text-[10px] font-bold text-[#71717a] uppercase block mb-1.5">
              Vector Card Title
            </label>
            <input
              type="text"
              value={cardTitle}
              onChange={(e) => setCardTitle(e.target.value)}
              className="w-full bg-[#111114] border border-white/[0.1] rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#10b981]"
            />
          </div>

          {/* LaTeX Formula Editor */}
          <div>
            <label className="font-mono text-[10px] font-bold text-[#71717a] uppercase block mb-1.5">
              LaTeX Math Formula
            </label>
            <textarea
              value={latexFormula}
              onChange={(e) => setLatexFormula(e.target.value)}
              rows={2}
              className="w-full bg-[#111114] border border-white/[0.1] rounded p-2.5 text-xs font-mono text-white focus:outline-none focus:border-[#10b981] resize-none"
            />
          </div>

          {/* Live KaTeX Inspector Preview */}
          <div className="bg-[#111114] p-3 rounded-lg border border-white/[0.08]">
            <span className="font-mono text-[9px] text-[#71717a] block mb-1">
              Live Inspector KaTeX Preview:
            </span>
            <div ref={inspectorKatexRef} className="text-white text-xs font-mono min-h-[20px]" />
          </div>

          {/* Accent Color Picker */}
          <div>
            <label className="font-mono text-[10px] font-bold text-[#71717a] uppercase block mb-1.5">
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
            <label className="font-mono text-[10px] font-bold text-[#71717a] uppercase block mb-1.5">
              Position Anchor
            </label>
            <div className="grid grid-cols-3 gap-1.5 font-mono text-[10px]">
              <button
                onClick={() => setCardPos('bottom_left')}
                className={`py-1.5 rounded border transition-all cursor-pointer ${
                  cardPos === 'bottom_left'
                    ? 'bg-[#18181b] text-white border-[#10b981] font-bold'
                    : 'bg-[#111114] text-[#71717a] border-white/[0.08]'
                }`}
              >
                Bottom Left
              </button>
              <button
                onClick={() => setCardPos('center')}
                className={`py-1.5 rounded border transition-all cursor-pointer ${
                  cardPos === 'center'
                    ? 'bg-[#18181b] text-white border-[#10b981] font-bold'
                    : 'bg-[#111114] text-[#71717a] border-white/[0.08]'
                }`}
              >
                Center
              </button>
              <button
                onClick={() => setCardPos('bottom_third')}
                className={`py-1.5 rounded border transition-all cursor-pointer ${
                  cardPos === 'bottom_third'
                    ? 'bg-[#18181b] text-white border-[#10b981] font-bold'
                    : 'bg-[#111114] text-[#71717a] border-white/[0.08]'
                }`}
              >
                Lower Third
              </button>
            </div>
          </div>
        </div>

        {/* 4K Vello Composite Action */}
        <button className="w-full bg-white hover:bg-[#e4e4e7] text-black font-extrabold text-xs py-3 rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_16px_rgba(255,255,255,0.15)] mt-4">
          <Sparkles className="w-3.5 h-3.5" />
          Export 4K Master (Vello Composite)
        </button>
      </aside>
    </div>
  );
}
