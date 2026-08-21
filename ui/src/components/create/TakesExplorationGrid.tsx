import { useState } from 'react';
import { 
  Play, 
  Loader2, 
  Download, 
  Copy, 
  Check, 
  Star, 
  Plus, 
  Scissors, 
  Film
} from 'lucide-react';

export interface TakeItem {
  id: number;
  seed: number;
  video_url: string;
  pan_deg?: number;
  zoom_ratio?: number;
  prompt?: string;
  duration_sec?: number;
  fps?: number;
  width?: number;
  height?: number;
}

interface TakesExplorationGridProps {
  takes?: TakeItem[];
  isGenerating?: boolean;
  activePrompt?: string;
  generationProgress?: number;
  generationPhase?: string;
  onSelectSeed?: (seed: number) => void;
}

export function TakesExplorationGrid({ 
  takes, 
  isGenerating,
  activePrompt = '',
  generationProgress = 0,
  generationPhase = 'DiT Sampling',
  onSelectSeed,
}: TakesExplorationGridProps) {
  const [copiedTakeId, setCopiedTakeId] = useState<number | null>(null);
  const [starredTakes, setStarredTakes] = useState<number[]>([]);
  const [hoveredTakeId, setHoveredTakeId] = useState<number | null>(null);

  const fallbackSeeds = [482910, 482911, 482912, 482913];

  const handleCopyPrompt = (take: TakeItem, e: React.MouseEvent) => {
    e.stopPropagation();
    const textToCopy = take.prompt || activePrompt;
    navigator.clipboard.writeText(textToCopy);
    setCopiedTakeId(take.id);
    setTimeout(() => {
      setCopiedTakeId(null);
    }, 2000);
  };

  const handleDownloadVideo = (take: TakeItem, e: React.MouseEvent) => {
    e.stopPropagation();
    const a = document.createElement('a');
    a.href = take.video_url;
    a.download = `spacepilot_take_${take.id}_seed_${take.seed}.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const toggleStarTake = (takeId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (starredTakes.includes(takeId)) {
      setStarredTakes(starredTakes.filter(id => id !== takeId));
    } else {
      setStarredTakes([...starredTakes, takeId]);
    }
  };

  // Determine current pipeline stage (1-5)
  let currentStage = 1;
  if (generationProgress >= 100) currentStage = 5;
  else if (generationProgress >= 85) currentStage = 4;
  else if (generationProgress >= 20) currentStage = 3;
  else if (generationProgress >= 10) currentStage = 2;

  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm hover:border-white/[0.14] transition-colors">
      <div className="flex justify-between items-center border-b border-white/[0.06] pb-3">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-cyan-400" />
          <h2 className="text-[13px] font-semibold text-white/70 uppercase tracking-wider">
            Takes &amp; Exploration Director Grid
          </h2>
        </div>
        <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
          {takes && takes.length > 0 ? `${takes.length} Takes Generated` : '4-Take Batch Explorer'}
        </span>
      </div>

      {/* Live Multi-Phase Generation Status Bar */}
      {isGenerating && (
        <div className="flex flex-col gap-3 p-4 bg-black/60 border border-white/[0.12] rounded-xl animate-in fade-in duration-200">
          <div className="flex justify-between items-center text-xs">
            <div className="flex items-center gap-2 text-cyan-400 font-semibold font-mono">
              <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              <span>{generationPhase} — {generationProgress}%</span>
            </div>
            <span className="font-mono text-white/40 text-[11px]">
              Resident GPU Worker (48GB L40S)
            </span>
          </div>

          {/* 5-Phase Pipeline Indicator */}
          <div className="grid grid-cols-5 gap-1 pt-1">
            {[
              { num: 1, label: 'Queued (0%)' },
              { num: 2, label: 'VRAM & Weights (15%)' },
              { num: 3, label: 'DiT Sampling (55%)' },
              { num: 4, label: 'VAE Latent (90%)' },
              { num: 5, label: 'Plate Ready (100%)' },
            ].map((stg) => {
              const isDone = currentStage > stg.num;
              const isActive = currentStage === stg.num;
              return (
                <div key={stg.num} className="flex flex-col items-center gap-1.5 text-center">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-bold transition-all ${
                    isDone 
                      ? 'bg-emerald-500 text-black shadow-[0_0_8px_rgba(16,185,129,0.5)]'
                      : isActive
                      ? 'bg-cyan-500 text-black shadow-[0_0_10px_rgba(6,182,212,0.8)] animate-pulse'
                      : 'bg-[#18181b] border border-white/[0.08] text-white/40'
                  }`}>
                    {isDone ? '✓' : stg.num}
                  </div>
                  <span className={`text-[9.5px] font-mono leading-tight ${
                    isDone ? 'text-emerald-400' : isActive ? 'text-cyan-400 font-bold' : 'text-white/30'
                  }`}>
                    {stg.label}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Progress Bar Track */}
          <div className="w-full h-1.5 bg-[#18181b] rounded-full overflow-hidden mt-1">
            <div 
              className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-300 rounded-full"
              style={{ width: `${Math.max(5, generationProgress)}%` }}
            />
          </div>
        </div>
      )}

      {/* Takes Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {takes && takes.length > 0 ? (
          takes.map((take) => {
            const isStarred = starredTakes.includes(take.id);
            const isCopied = copiedTakeId === take.id;
            return (
              <div 
                key={take.id} 
                onMouseEnter={() => setHoveredTakeId(take.id)}
                onMouseLeave={() => setHoveredTakeId(null)}
                className="relative aspect-video bg-[#111114] rounded-xl border border-white/[0.12] overflow-hidden group hover:border-cyan-500/50 transition-all shadow-md"
              >
                {/* Take Video Player */}
                <video 
                  src={take.video_url} 
                  className="w-full h-full object-cover" 
                  controls 
                  autoPlay={hoveredTakeId === take.id}
                  loop 
                  muted 
                  playsInline
                />

                {/* Top Badge: Take ID, Seed, Star */}
                <div className="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none">
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-black/80 font-mono text-[10.5px] text-white/90 border border-white/10 backdrop-blur-md">
                    <span>Take #{take.id}</span>
                    <span className="text-white/30">·</span>
                    <span className="text-cyan-400">Seed {take.seed}</span>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => toggleStarTake(take.id, e)}
                    className={`pointer-events-auto p-1.5 rounded-md backdrop-blur-md transition-all cursor-pointer ${
                      isStarred
                        ? 'bg-amber-500 text-black shadow-[0_0_8px_rgba(245,158,11,0.6)]'
                        : 'bg-black/70 text-white/60 hover:text-amber-400 hover:bg-black/90 border border-white/10'
                    }`}
                    title={isStarred ? 'Unstar Best Take' : 'Star / Mark Best Take'}
                  >
                    <Star className={`w-3.5 h-3.5 ${isStarred ? 'fill-black' : ''}`} />
                  </button>
                </div>

                {/* Hover Action Overlay Toolbar */}
                <div className="absolute bottom-0 left-0 right-0 p-2.5 bg-gradient-to-t from-black/95 via-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1">
                    {/* Direct Take Download Button */}
                    <button
                      type="button"
                      onClick={(e) => handleDownloadVideo(take, e)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-white/10 hover:bg-emerald-500 hover:text-black text-white text-[11px] font-bold backdrop-blur-md transition-all cursor-pointer shadow-sm"
                      title="Download MP4 video take directly"
                    >
                      <Download className="w-3 h-3" />
                      <span>Download</span>
                    </button>

                    {/* Prompt Copy Button on Hover */}
                    <button
                      type="button"
                      onClick={(e) => handleCopyPrompt(take, e)}
                      className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-semibold backdrop-blur-md transition-all cursor-pointer ${
                        isCopied
                          ? 'bg-cyan-500 text-black font-bold'
                          : 'bg-white/10 hover:bg-white/20 text-white'
                      }`}
                      title="Copy generation prompt & recipe"
                    >
                      {isCopied ? <Check className="w-3 h-3 text-black" /> : <Copy className="w-3 h-3" />}
                      <span>{isCopied ? 'Copied' : 'Prompt'}</span>
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    {/* Extend Take (+4s) */}
                    <a
                      href={`/create?extend_id=${take.id}`}
                      className="flex items-center gap-1 px-2 py-1.5 rounded-md bg-white/10 hover:bg-cyan-500 hover:text-black text-white text-[11px] font-semibold backdrop-blur-md transition-all cursor-pointer"
                      title="Extend take duration (+4s)"
                    >
                      <Plus className="w-3 h-3" />
                      <span>Extend</span>
                    </a>

                    {/* Open in Pro Studio Timeline */}
                    <a
                      href={`/studio?asset_id=${take.id}`}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-white/10 hover:bg-purple-500 hover:text-white text-white text-[11px] font-semibold backdrop-blur-md transition-all cursor-pointer"
                      title="Open clip in Spacepilot Pro Studio Timeline"
                    >
                      <Scissors className="w-3 h-3" />
                      <span>Editor</span>
                    </a>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          fallbackSeeds.map((seed, idx) => (
            <div 
              key={seed} 
              className="relative aspect-video bg-[#111114] rounded-xl border border-white/[0.08] overflow-hidden group hover:border-amber-500/50 transition-all cursor-pointer"
            >
              <div className="absolute inset-0 flex flex-col items-center justify-center text-white/25 gap-1.5">
                <div className="w-10 h-10 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-white/40 group-hover:text-amber-400 group-hover:border-amber-500/30 transition-all">
                  <Play className="w-4 h-4 ml-0.5" />
                </div>
                <span className="font-mono text-[11px]">Director Take #{idx + 1} Slot</span>
              </div>
              
              <div className="absolute bottom-0 left-0 right-0 p-2.5 bg-gradient-to-t from-black/95 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex justify-between items-center">
                <span className="text-[11px] font-mono text-white/70">Seed: #{seed}</span>
                <button 
                  type="button"
                  onClick={() => onSelectSeed && onSelectSeed(seed)}
                  className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500 hover:text-black text-amber-400 text-[11px] font-bold rounded border border-amber-500/30 transition-colors cursor-pointer"
                >
                  Load Seed #{seed}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

