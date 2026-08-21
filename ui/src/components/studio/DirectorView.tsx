import { 
  Plus, 
  Film, 
  Play, 
  Sparkles, 
  Trash2,
  Compass
} from 'lucide-react';
import { useStudioStore } from '../../stores/studioStore';
import { useTimelineStore } from '../../stores/timelineStore';

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

  const { isPlaying, togglePlay } = useTimelineStore();

  const activeScene = scenes.find((s) => s.id === activeSceneId) || scenes[0];

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-black font-sans select-none">
      {/* Storyboard Hero Bar */}
      <div className="h-12 bg-[#09090b] border-b border-white/10 px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
            <Film className="w-3.5 h-3.5 text-emerald-400" />
            AI Director Storyboard Reel
          </span>
          <span className="font-mono text-[10px] text-white/50 bg-white/5 px-2 py-0.5 rounded border border-white/10">
            {scenes.length} Scenes · {(scenes.reduce((acc, s) => acc + s.duration, 0)).toFixed(1)}s Runtime
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => addScene('New cinematic scene description...')}
            className="flex items-center gap-1.5 text-xs font-mono bg-[#18181b] hover:bg-[#222226] border border-white/10 px-3 py-1.5 rounded-lg text-white transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            Add Scene
          </button>
          <button
            disabled={isGenerating}
            className="flex items-center gap-1.5 text-xs font-bold bg-white text-black hover:bg-zinc-200 px-4 py-1.5 rounded-lg transition-all shadow-[0_0_16px_rgba(255,255,255,0.15)] cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Batch Render (L40S)
          </button>
        </div>
      </div>

      {/* Storyboard Scenes Filmstrip */}
      <div className="h-32 bg-[#09090b]/80 border-b border-white/10 p-3 flex items-center gap-3 overflow-x-auto select-none shrink-0 scrollbar-hide">
        {scenes.map((scene, idx) => (
          <div
            key={scene.id}
            onClick={() => setActiveSceneId(scene.id)}
            className={`h-full w-56 rounded-xl border p-2.5 flex flex-col justify-between shrink-0 cursor-pointer transition-all ${
              activeSceneId === scene.id
                ? 'bg-[#18181b] border-emerald-400 shadow-[0_0_16px_rgba(16,185,129,0.2)] ring-1 ring-emerald-400'
                : 'bg-[#111114] border-white/10 hover:border-white/20'
            }`}
          >
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="font-bold text-white flex items-center gap-1">
                SCENE {idx + 1}
              </span>
              <span className="text-white/40">{scene.duration}s</span>
            </div>

            <p className="text-[11px] text-white/70 line-clamp-2 leading-tight font-sans">
              {scene.prompt}
            </p>

            <div className="flex items-center justify-between text-[9px] font-mono text-white/50">
              <span>Pan: {scene.panDeg > 0 ? `+${scene.panDeg}°` : `${scene.panDeg}°`}</span>
              <span className={`font-bold ${scene.status === 'ready' ? 'text-emerald-400' : 'text-amber-400'}`}>
                {scene.status.toUpperCase()}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Active Scene Director Canvas & Inspector */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* Left: Active Scene Configuration */}
        <div className="col-span-12 lg:col-span-4 bg-[#09090b] border-r border-white/10 p-5 flex flex-col justify-between overflow-y-auto">
          <div className="flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <span className="font-mono text-xs font-bold text-white/70 uppercase tracking-wider">
                Scene Prompt & Camera Guidance
              </span>
              {scenes.length > 1 && (
                <button
                  onClick={() => removeScene(activeScene.id)}
                  className="text-rose-400 hover:text-rose-300 text-xs flex items-center gap-1 font-mono cursor-pointer"
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
              className="w-full bg-[#111114] border border-white/10 rounded-xl p-3 text-xs leading-relaxed text-white focus:outline-none focus:border-emerald-400 transition-all resize-none font-sans"
            />

            {/* 3D Camera Controls */}
            <div className="bg-[#111114] p-4 rounded-xl border border-white/10 flex flex-col gap-3 font-mono text-xs">
              <div className="font-bold text-white flex justify-between">
                <span className="flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-emerald-400" />
                  Camera Orbit (STG Guidance)
                </span>
                <span className="text-emerald-400">+{activeScene.panDeg}°</span>
              </div>
              <input
                type="range"
                min="-45"
                max="45"
                value={activeScene.panDeg}
                onChange={() => {}}
                className="w-full accent-emerald-400 cursor-pointer"
              />
            </div>
          </div>

          <button 
            onClick={togglePlay}
            className="w-full bg-white hover:bg-zinc-200 text-black font-extrabold text-xs py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_16px_rgba(255,255,255,0.15)] mt-4"
          >
            {isPlaying ? <span className="fill-black font-bold">❚❚ Pause Scene</span> : <><Play className="w-3.5 h-3.5 fill-black" /><span>Audition Scene ({activeScene.duration}s)</span></>}
          </button>
        </div>

        {/* Right: Active Scene Video Preview */}
        <div className="col-span-12 lg:col-span-8 bg-black p-6 flex flex-col justify-center items-center relative">
          <div className="w-full max-w-2xl aspect-video bg-[#09090b] border border-white/10 rounded-2xl flex flex-col justify-between p-4 relative overflow-hidden shadow-2xl">
            <div className="flex justify-between items-center z-10 font-mono text-xs">
              <span className="bg-black/80 px-2.5 py-1 rounded-lg border border-white/10 text-white font-bold">
                SCENE PREVIEW · LTX-2.5 48GB
              </span>
              <span className="text-emerald-400 font-bold bg-emerald-500/15 px-2.5 py-1 rounded-lg border border-emerald-500/30">
                PRORES 422
              </span>
            </div>

            <div className="flex justify-center items-center z-10">
              <button 
                onClick={togglePlay}
                className="w-14 h-14 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 flex items-center justify-center transition-all cursor-pointer backdrop-blur-md"
              >
                {isPlaying ? <span className="text-white font-bold text-lg">❚❚</span> : <Play className="w-6 h-6 fill-white text-white ml-1" />}
              </button>
            </div>

            <div className="flex justify-between items-end z-10 font-mono text-xs text-white/50">
              <span>Resolution: 1920×1080 @ 24fps</span>
              <span className="text-white">00:00:0{activeScene.duration.toFixed(0)}:00</span>
            </div>

            {/* Subtle Gradient Film Overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 pointer-events-none" />
          </div>
        </div>
      </div>
    </div>
  );
}
