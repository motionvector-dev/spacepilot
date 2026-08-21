import { 
  Plus, 
  Film, 
  Play, 
  Sparkles, 
  Trash2
} from 'lucide-react';
import { useStudioStore } from '../../stores/studioStore';

export default function DirectorView() {
  const { 
    scenes, 
    activeSceneId, 
    setActiveSceneId, 
    addScene, 
    removeScene,
    updateScenePrompt,
    isGenerating
  } = useStudioStore();

  const activeScene = scenes.find((s) => s.id === activeSceneId) || scenes[0];

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-black font-sans">
      {/* Storyboard Hero Bar */}
      <div className="h-14 bg-[#09090b] border-b border-white/[0.08] px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
            <Film className="w-3.5 h-3.5 text-[#10b981]" />
            Multi-Scene Storyboard Reel
          </span>
          <span className="font-mono text-[10px] text-[#71717a] bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.08]">
            {scenes.length} Scenes · {(scenes.reduce((acc, s) => acc + s.duration, 0)).toFixed(1)}s Total Runtime
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => addScene('New cinematic scene description...')}
            className="flex items-center gap-1.5 text-xs font-mono bg-[#18181b] hover:bg-[#222226] border border-white/[0.1] px-3 py-1.5 rounded text-white transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-[#10b981]" />
            Add Scene
          </button>
          <button
            disabled={isGenerating}
            className="flex items-center gap-1.5 text-xs font-bold bg-white text-black hover:bg-[#e4e4e7] px-4 py-1.5 rounded transition-all shadow-[0_0_16px_rgba(255,255,255,0.15)] cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Batch Render Reel
          </button>
        </div>
      </div>

      {/* Storyboard Scenes Filmstrip */}
      <div className="h-36 bg-[#09090b]/60 border-b border-white/[0.08] p-3 flex items-center gap-3 overflow-x-auto select-none shrink-0">
        {scenes.map((scene, idx) => (
          <div
            key={scene.id}
            onClick={() => setActiveSceneId(scene.id)}
            className={`h-full w-56 rounded-lg border p-2.5 flex flex-col justify-between shrink-0 cursor-pointer transition-all ${
              activeSceneId === scene.id
                ? 'bg-[#18181b] border-[#10b981] shadow-[0_0_16px_rgba(16,185,129,0.2)] ring-1 ring-[#10b981]'
                : 'bg-[#111114] border-white/[0.08] hover:border-white/[0.2]'
            }`}
          >
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="font-bold text-white flex items-center gap-1">
                SCENE {idx + 1}
              </span>
              <span className="text-[#71717a]">{scene.duration}s</span>
            </div>

            <p className="text-[11px] text-[#a1a1aa] line-clamp-2 leading-tight font-sans">
              {scene.prompt}
            </p>

            <div className="flex items-center justify-between text-[9px] font-mono text-[#71717a]">
              <span>Pan: +{scene.panDeg}°</span>
              <span className={`font-bold ${scene.status === 'ready' ? 'text-[#10b981]' : 'text-[#f59e0b]'}`}>
                {scene.status.toUpperCase()}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Active Scene Director Canvas & Inspector */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* Left: Active Scene Configuration */}
        <div className="col-span-12 lg:col-span-4 bg-[#09090b] border-r border-white/[0.08] p-6 flex flex-col justify-between overflow-y-auto">
          <div className="flex flex-col gap-5">
            <div className="flex justify-between items-center">
              <span className="font-mono text-xs font-bold text-[#a1a1aa] uppercase tracking-wider">
                Scene Prompt & Camera Guidance
              </span>
              {scenes.length > 1 && (
                <button
                  onClick={() => removeScene(activeScene.id)}
                  className="text-[#f43f5e] hover:text-[#f43f5e]/80 text-xs flex items-center gap-1 font-mono cursor-pointer"
                >
                  <Trash2 className="w-3 h-3" />
                  Delete Scene
                </button>
              )}
            </div>

            <textarea
              value={activeScene.prompt}
              onChange={(e) => updateScenePrompt(activeScene.id, e.target.value)}
              rows={4}
              className="w-full bg-[#111114] border border-white/[0.1] rounded-lg p-3 text-xs leading-relaxed text-white focus:outline-none focus:border-[#10b981] transition-all resize-none font-sans"
            />

            {/* 3D Camera Controls */}
            <div className="bg-[#111114] p-4 rounded-xl border border-white/[0.08] flex flex-col gap-4 font-mono text-xs">
              <div className="font-bold text-white flex justify-between">
                <span>Camera Orbit (STG Guidance)</span>
                <span className="text-[#10b981]">+{activeScene.panDeg}°</span>
              </div>
              <input
                type="range"
                min="-45"
                max="45"
                value={activeScene.panDeg}
                onChange={() => {}}
                className="w-full accent-[#10b981] cursor-pointer"
              />
            </div>
          </div>

          <button className="w-full bg-white hover:bg-[#e4e4e7] text-black font-extrabold text-xs py-3 rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_16px_rgba(255,255,255,0.15)]">
            <Play className="w-3.5 h-3.5 fill-black" />
            Audition Scene ({activeScene.duration}s)
          </button>
        </div>

        {/* Right: Active Scene Video Preview */}
        <div className="col-span-12 lg:col-span-8 bg-black p-6 flex flex-col justify-center items-center">
          <div className="w-full max-w-2xl aspect-video bg-[#09090b] border border-white/[0.1] rounded-xl flex flex-col justify-between p-4 relative overflow-hidden shadow-2xl">
            <div className="flex justify-between items-center z-10 font-mono text-xs">
              <span className="bg-black/80 px-2.5 py-1 rounded border border-white/[0.08] text-white font-bold">
                SCENE PREVIEW · LTX-2.5 48GB
              </span>
              <span className="text-[#10b981] font-bold bg-[#10b981]/15 px-2 py-0.5 rounded border border-[#10b981]/30">
                PRORES 422
              </span>
            </div>

            <div className="flex justify-center items-center z-10">
              <button className="w-12 h-12 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 flex items-center justify-center transition-all cursor-pointer backdrop-blur-md">
                <Play className="w-5 h-5 fill-white text-white ml-0.5" />
              </button>
            </div>

            <div className="flex justify-between items-end z-10 font-mono text-xs text-[#71717a]">
              <span>Resolution: 1920×1080 @ 24fps</span>
              <span className="text-white">00:00:0{activeScene.duration}:00</span>
            </div>

            {/* Subtle Gradient Film Overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30" />
          </div>
        </div>
      </div>
    </div>
  );
}
