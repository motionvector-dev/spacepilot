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
    <div className="flex-1 flex flex-col overflow-hidden bg-ground font-sans select-none">
      {/* Storyboard Hero Bar */}
      <div className="h-12 bg-surface border-b border-line-200 px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-1.5">
            <Film className="w-3.5 h-3.5 text-verify" />
            AI Director Storyboard Reel
          </span>
          <span className="font-mono text-[10px] text-ink-500 bg-inset px-2 py-0.5 rounded border border-line-200">
            {scenes.length} Scenes · {(scenes.reduce((acc, s) => acc + s.duration, 0)).toFixed(1)}s Runtime
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => addScene('New cinematic scene description...')}
            className="flex items-center gap-1.5 text-xs font-mono bg-inset hover:bg-strong border border-line-200 px-3 py-1.5 rounded-lg text-ink transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-verify" />
            Add Scene
          </button>
          <button
            disabled={isGenerating}
            className="flex items-center gap-1.5 text-xs font-bold bg-accent text-accent-contrast hover:brightness-110 px-4 py-1.5 rounded-lg transition-all cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Batch Render (L40S)
          </button>
        </div>
      </div>

      {/* Storyboard Scenes Filmstrip */}
      <div className="h-32 bg-surface/80 border-b border-line-200 p-3 flex items-center gap-3 overflow-x-auto select-none shrink-0 scrollbar-hide">
        {scenes.map((scene, idx) => (
          <div
            key={scene.id}
            onClick={() => setActiveSceneId(scene.id)}
            className={`h-full w-56 rounded-xl border p-2.5 flex flex-col justify-between shrink-0 cursor-pointer transition-all ${
              activeSceneId === scene.id
                ? 'bg-inset border-verify ring-1 ring-verify'
                : 'bg-raised border-line-200 hover:border-line-300'
            }`}
          >
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="font-bold text-ink flex items-center gap-1">
                SCENE {idx + 1}
              </span>
              <span className="text-ink-500">{scene.duration}s</span>
            </div>

            <p className="text-[11px] text-ink-700 line-clamp-2 leading-tight font-sans">
              {scene.prompt}
            </p>

            <div className="flex items-center justify-between text-[9px] font-mono text-ink-500">
              <span>Pan: {scene.panDeg > 0 ? `+${scene.panDeg}°` : `${scene.panDeg}°`}</span>
              <span className={`font-bold ${scene.status === 'ready' ? 'text-verify' : 'text-ink-900'}`}>
                {scene.status.toUpperCase()}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Active Scene Director Canvas & Inspector */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* Left: Active Scene Configuration */}
        <div className="col-span-12 lg:col-span-4 bg-surface border-r border-line-200 p-5 flex flex-col justify-between overflow-y-auto">
          <div className="flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <span className="font-mono text-xs font-bold text-ink-700 uppercase tracking-wider">
                Scene Prompt & Camera Guidance
              </span>
              {scenes.length > 1 && (
                <button
                  onClick={() => removeScene(activeScene.id)}
                  className="text-danger hover:text-danger/80 text-xs flex items-center gap-1 font-mono cursor-pointer"
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
              className="w-full bg-raised border border-line-200 rounded-xl p-3 text-xs leading-relaxed text-ink focus:outline-none focus:border-verify transition-all resize-none font-sans"
            />

            {/* 3D Camera Controls */}
            <div className="bg-raised p-4 rounded-xl border border-line-200 flex flex-col gap-3 font-mono text-xs">
              <div className="font-bold text-ink flex justify-between">
                <span className="flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-verify" />
                  Camera Orbit (STG Guidance)
                </span>
                <span className="text-verify">+{activeScene.panDeg}°</span>
              </div>
              <input
                type="range"
                min="-45"
                max="45"
                value={activeScene.panDeg}
                onChange={() => {}}
                className="w-full accent-verify cursor-pointer"
              />
            </div>
          </div>

          <button
            onClick={togglePlay}
            className="w-full bg-accent hover:brightness-110 text-accent-contrast font-extrabold text-xs py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer mt-4"
          >
            {isPlaying ? <span className="fill-accent-contrast font-bold">❚❚ Pause Scene</span> : <><Play className="w-3.5 h-3.5 fill-accent-contrast" /><span>Audition Scene ({activeScene.duration}s)</span></>}
          </button>
        </div>

        {/* Right: Active Scene Video Preview */}
        <div className="col-span-12 lg:col-span-8 bg-ground p-6 flex flex-col justify-center items-center relative">
          <div className="w-full max-w-2xl aspect-video bg-surface border border-line-200 rounded-2xl flex flex-col justify-between p-4 relative overflow-hidden">
            <div className="flex justify-between items-center z-10 font-mono text-xs">
              <span className="bg-ground/80 px-2.5 py-1 rounded-lg border border-line-200 text-ink font-bold">
                SCENE PREVIEW · LTX-2.5 48GB
              </span>
              <span className="text-verify font-bold bg-verify-soft px-2.5 py-1 rounded-lg border border-verify/30">
                PRORES 422
              </span>
            </div>

            <div className="flex justify-center items-center z-10">
              <button
                onClick={togglePlay}
                className="w-14 h-14 rounded-full bg-inset hover:bg-strong border border-line-300 flex items-center justify-center transition-all cursor-pointer backdrop-blur-md"
              >
                {isPlaying ? <span className="text-ink font-bold text-lg">❚❚</span> : <Play className="w-6 h-6 fill-ink text-ink ml-1" />}
              </button>
            </div>

            <div className="flex justify-between items-end z-10 font-mono text-xs text-ink-500">
              <span>Resolution: 1920×1080 @ 24fps</span>
              <span className="text-ink">00:00:0{activeScene.duration.toFixed(0)}:00</span>
            </div>

            {/* Film vignette scrim (black-to-transparent, not a hue gradient) kept for legibility of overlay text */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 pointer-events-none" />
          </div>
        </div>
      </div>
    </div>
  );
}
