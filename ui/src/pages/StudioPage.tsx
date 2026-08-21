import { 
  Sparkles, 
  Sliders, 
  Download, 
  Terminal, 
  Film, 
  Layers, 
  Volume2,
  Play
} from 'lucide-react';
import { useStudioStore } from '../stores/studioStore';
import { useGpuStore } from '../stores/gpuStore';
import TimelineEditor from '../components/studio/TimelineEditor';

export default function StudioPage() {
  const { 
    prompt, 
    setPrompt, 
    panAngle, 
    setPanAngle, 
    zoomRatio, 
    setZoomRatio, 
    selectedTakeId, 
    setSelectedTakeId, 
    takes, 
    voicePreset,
    setVoicePreset,
    musicLufs,
    isGenerating
  } = useStudioStore();

  const { status: gpuStatus } = useGpuStore();

  return (
    <div className="min-h-screen bg-black text-[#fafafa] flex flex-col font-sans">
      {/* Studio Top Control Bar */}
      <header className="h-14 bg-[#09090b] border-b border-white/[0.08] px-6 flex items-center justify-between z-20">
        <div className="flex items-center gap-4">
          <a href="/" className="flex items-center gap-2 text-sm font-extrabold tracking-tight">
            <span>🛸</span>
            <span>SpacePilot Studio</span>
          </a>
          <div className="h-4 w-px bg-white/[0.1]" />
          <div className="flex items-center gap-2 font-mono text-xs text-[#a1a1aa]">
            <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
            <span>{gpuStatus.instanceType.toUpperCase()} (L40S 48GB) · 0.0s Resident Daemon</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button className="flex items-center gap-1.5 text-xs font-mono bg-[#18181b] hover:bg-[#222226] border border-white/[0.1] px-3 py-1.5 rounded text-[#a1a1aa] hover:text-white transition-all cursor-pointer">
            <Terminal className="w-3.5 h-3.5 text-[#38bdf8]" />
            Cockpit SSH
          </button>
          <button className="flex items-center gap-1.5 text-xs font-semibold bg-white text-black px-4 py-1.5 rounded hover:bg-[#e4e4e7] transition-all shadow-[0_0_16px_rgba(255,255,255,0.15)] cursor-pointer">
            <Download className="w-3.5 h-3.5" />
            Export Master
          </button>
        </div>
      </header>

      {/* Main Studio Workstation Layout */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* Left Director Controls Sidebar */}
        <aside className="col-span-12 lg:col-span-4 bg-[#09090b] border-r border-white/[0.08] p-6 flex flex-col justify-between gap-6 overflow-y-auto">
          <div className="flex flex-col gap-6">
            {/* Prompt Input */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="font-mono text-xs font-bold text-[#a1a1aa] uppercase tracking-wider flex items-center gap-1.5">
                  <Film className="w-3.5 h-3.5 text-[#10b981]" />
                  Director Prompt & Vision
                </label>
                <span className="font-mono text-[10px] text-[#71717a]">LTX-2.5 Float8</span>
              </div>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                className="w-full bg-[#111114] border border-white/[0.1] rounded-lg p-3 text-xs leading-relaxed text-[#fafafa] focus:outline-none focus:border-[#10b981] transition-all resize-none font-sans"
              />
            </div>

            {/* 3D Camera Trajectory Compass Controls */}
            <div className="bg-[#111114] p-4 rounded-xl border border-white/[0.08] flex flex-col gap-4">
              <div className="font-mono text-xs font-bold text-white flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-[#06b6d4]" />
                  3D Camera Trajectory
                </span>
                <span className="text-[10px] text-[#06b6d4] bg-[#06b6d4]/10 border border-[#06b6d4]/30 px-1.5 py-0.5 rounded font-mono">
                  STG Vector Scaled
                </span>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono text-[#a1a1aa] mb-1.5">
                  <span>Pan Angle (Horizontal Orbit)</span>
                  <span className="text-[#10b981] font-bold">+{panAngle}°</span>
                </div>
                <input 
                  type="range" 
                  min="-45" 
                  max="45" 
                  value={panAngle} 
                  onChange={(e) => setPanAngle(Number(e.target.value))}
                  className="w-full accent-[#10b981] cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono text-[#a1a1aa] mb-1.5">
                  <span>Zoom / Dolly Ratio</span>
                  <span className="text-[#06b6d4] font-bold">{zoomRatio}x</span>
                </div>
                <input 
                  type="range" 
                  min="1.0" 
                  max="2.5" 
                  step="0.1"
                  value={zoomRatio} 
                  onChange={(e) => setZoomRatio(Number(e.target.value))}
                  className="w-full accent-[#06b6d4] cursor-pointer"
                />
              </div>
            </div>

            {/* In-Process Audio & Voice Mastering */}
            <div className="bg-[#111114] p-4 rounded-xl border border-white/[0.08] flex flex-col gap-3">
              <div className="font-mono text-xs font-bold text-white flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Volume2 className="w-3.5 h-3.5 text-[#a855f7]" />
                  Kokoro-82M Voice & Mastering
                </span>
                <span className="text-[10px] text-[#a855f7] bg-[#a855f7]/10 border border-[#a855f7]/30 px-1.5 py-0.5 rounded font-mono">
                  2-Pass EBU R128
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                <div>
                  <label className="text-[#71717a] text-[10px] block mb-1">Voice Preset</label>
                  <select 
                    value={voicePreset} 
                    onChange={(e) => setVoicePreset(e.target.value)}
                    className="w-full bg-[#18181b] border border-white/[0.1] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none"
                  >
                    <option value="af_bella">af_bella (US Female)</option>
                    <option value="af_sarah">af_sarah (US Female)</option>
                    <option value="am_adam">am_adam (US Male)</option>
                    <option value="bf_emma">bf_emma (British)</option>
                  </select>
                </div>

                <div>
                  <label className="text-[#71717a] text-[10px] block mb-1">Target Loudness</label>
                  <div className="flex items-center justify-between bg-[#18181b] border border-white/[0.1] rounded px-2.5 py-1.5">
                    <span className="text-[#10b981] font-bold">{musicLufs}</span>
                    <span className="text-[10px] text-[#71717a]">LUFS</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Dispatch Button */}
          <button 
            disabled={isGenerating}
            className="w-full bg-white hover:bg-[#e4e4e7] text-black font-extrabold text-sm py-3.5 rounded-lg transition-all flex items-center justify-center gap-2 shadow-[0_0_24px_rgba(255,255,255,0.15)] disabled:opacity-50 cursor-pointer"
          >
            <Sparkles className="w-4 h-4" />
            <span>Generate 4-Take Grid</span>
            <span className="font-mono text-xs text-[#71717a] ml-1">(4s @ 24fps)</span>
          </button>
        </aside>

        {/* Right 2x2 Director Canvas & Player Viewport */}
        <section className="col-span-12 lg:col-span-8 bg-black p-6 flex flex-col justify-between gap-6 overflow-y-auto">
          <div>
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-[#10b981]" />
                  4-Take Director Exploration Matrix
                </span>
                <span className="font-mono text-[11px] text-[#71717a]">· Multi-Take Synchronized Audition</span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-[#a1a1aa]">Active Seed:</span>
                <span className="text-xs font-mono font-bold text-[#10b981] bg-[#10b981]/10 px-2 py-0.5 rounded border border-[#10b981]/30">
                  {takes.find(t => t.id === selectedTakeId)?.seed}
                </span>
              </div>
            </div>

            {/* 2x2 Video Exploration Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {takes.map((take) => (
                <div
                  key={take.id}
                  onClick={() => setSelectedTakeId(take.id)}
                  className={`cursor-pointer bg-[#09090b] rounded-xl p-4 border transition-all flex flex-col justify-between aspect-video relative overflow-hidden group ${
                    selectedTakeId === take.id 
                      ? 'border-[#10b981] shadow-[0_0_24px_rgba(16,185,129,0.25)] ring-1 ring-[#10b981]' 
                      : 'border-white/[0.08] hover:border-white/[0.2]'
                  }`}
                >
                  <div className="flex justify-between items-center z-10">
                    <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-black/80 border border-white/[0.08] text-white">
                      TAKE {take.id} · SEED {take.seed}
                    </span>
                    {selectedTakeId === take.id && (
                      <span className="font-mono text-[10px] font-bold text-[#10b981] bg-[#10b981]/15 px-2 py-0.5 rounded border border-[#10b981]/40">
                        DIRECTOR PICK
                      </span>
                    )}
                  </div>

                  <div className="flex justify-between items-end font-mono text-[11px] text-[#71717a] z-10">
                    <span className="text-[#a1a1aa]">Pan: +{take.panDeg}° · Zoom: {take.zoomRatio}x</span>
                    <span className="text-white flex items-center gap-1 bg-black/60 px-2 py-0.5 rounded border border-white/[0.08]">
                      <Play className="w-2.5 h-2.5 fill-white" /> 4.0s
                    </span>
                  </div>

                  {/* Playhead Hover Overlay */}
                  <div className="absolute inset-0 bg-gradient-to-tr from-black/80 via-transparent to-white/[0.04] group-hover:opacity-80 transition-opacity" />
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* Multi-Track NLE Timeline Editor */}
      <TimelineEditor />
    </div>
  );
}
