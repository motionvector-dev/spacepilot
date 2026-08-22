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
    <div className="flex flex-col gap-4 p-5 bg-surface border border-line-200 rounded-xl hover:border-line-300 transition-colors">
      <div className="flex justify-between items-center border-b border-line-100 pb-3">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-ink-700" />
          <h2 className="text-[13px] font-semibold text-ink-700 uppercase tracking-wider">
            Takes &amp; Exploration Director Grid
          </h2>
        </div>
        <span className="text-[11px] font-mono text-verify bg-verify-soft px-2 py-0.5 rounded border border-verify/20">
          {takes && takes.length > 0 ? `${takes.length} Takes Generated` : '4-Take Batch Explorer'}
        </span>
      </div>

      {/* Live Multi-Phase Generation Status Bar */}
      {isGenerating && (
        <div className="flex flex-col gap-3 p-4 bg-inset border border-line-300 rounded-xl animate-in fade-in duration-200">
          <div className="flex justify-between items-center text-xs">
            <div className="flex items-center gap-2 text-ink-900 font-semibold font-mono">
              <Loader2 className="w-4 h-4 animate-spin text-ink-900" />
              <span>{generationPhase} — {generationProgress}%</span>
            </div>
            <span className="font-mono text-ink-500 text-[11px]">
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
                      ? 'bg-verify-soft text-verify border border-verify'
                      : isActive
                      ? 'bg-strong border border-line-500 text-ink animate-pulse'
                      : 'bg-inset border border-line-200 text-ink-500'
                  }`}>
                    {isDone ? '✓' : stg.num}
                  </div>
                  <span className={`text-[9.5px] font-mono leading-tight ${
                    isDone ? 'text-verify' : isActive ? 'text-ink font-bold' : 'text-ink-300'
                  }`}>
                    {stg.label}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Progress Bar Track */}
          <div className="w-full h-1.5 bg-strong rounded-full overflow-hidden mt-1">
            <div
              className="h-full bg-verify transition-all duration-300 rounded-full"
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
                className="relative aspect-video bg-raised rounded-xl border border-line-300 overflow-hidden group hover:border-line-400 transition-all"
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
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-ground/80 font-mono text-[10.5px] text-ink-900 border border-line-200 backdrop-blur-md">
                    <span>Take #{take.id}</span>
                    <span className="text-ink-300">·</span>
                    <span className="text-ink-700">Seed {take.seed}</span>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => toggleStarTake(take.id, e)}
                    className={`pointer-events-auto p-1.5 rounded-md backdrop-blur-md transition-all cursor-pointer ${
                      isStarred
                        ? 'bg-strong text-ink border border-line-500'
                        : 'bg-ground/70 text-ink-700 hover:text-ink-900 hover:bg-ground/90 border border-line-200'
                    }`}
                    title={isStarred ? 'Unstar Best Take' : 'Star / Mark Best Take'}
                  >
                    <Star className={`w-3.5 h-3.5 ${isStarred ? 'fill-ink' : ''}`} />
                  </button>
                </div>

                {/* Hover Action Overlay Toolbar */}
                <div className="absolute bottom-0 left-0 right-0 p-2.5 bg-gradient-to-t from-ground/95 via-ground/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1">
                    {/* Direct Take Download Button */}
                    <button
                      type="button"
                      onClick={(e) => handleDownloadVideo(take, e)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-inset/70 hover:bg-strong text-ink text-[11px] font-bold backdrop-blur-md transition-all cursor-pointer"
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
                          ? 'bg-strong text-ink font-bold'
                          : 'bg-inset/70 hover:bg-inset text-ink'
                      }`}
                      title="Copy generation prompt & recipe"
                    >
                      {isCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      <span>{isCopied ? 'Copied' : 'Prompt'}</span>
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    {/* Extend Take (+4s) */}
                    <a
                      href={`/create?extend_id=${take.id}`}
                      className="flex items-center gap-1 px-2 py-1.5 rounded-md bg-inset/70 hover:bg-strong text-ink text-[11px] font-semibold backdrop-blur-md transition-all cursor-pointer"
                      title="Extend take duration (+4s)"
                    >
                      <Plus className="w-3 h-3" />
                      <span>Extend</span>
                    </a>

                    {/* Open in Pro Studio Timeline */}
                    <a
                      href={`/studio?asset_id=${take.id}`}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-inset/70 hover:bg-strong text-ink text-[11px] font-semibold backdrop-blur-md transition-all cursor-pointer"
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
              className="relative aspect-video bg-raised rounded-xl border border-line-200 overflow-hidden group hover:border-line-400 transition-all cursor-pointer"
            >
              <div className="absolute inset-0 flex flex-col items-center justify-center text-ink-300 gap-1.5">
                <div className="w-10 h-10 rounded-full bg-inset border border-line-200 flex items-center justify-center text-ink-500 group-hover:text-ink-900 group-hover:border-line-400 transition-all">
                  <Play className="w-4 h-4 ml-0.5" />
                </div>
                <span className="font-mono text-[11px]">Director Take #{idx + 1} Slot</span>
              </div>

              <div className="absolute bottom-0 left-0 right-0 p-2.5 bg-gradient-to-t from-ground/95 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex justify-between items-center">
                <span className="text-[11px] font-mono text-ink-700">Seed: #{seed}</span>
                <button
                  type="button"
                  onClick={() => onSelectSeed && onSelectSeed(seed)}
                  className="px-2.5 py-1 bg-accent-soft hover:bg-accent hover:text-accent-contrast text-ink text-[11px] font-bold rounded border border-accent-border transition-colors cursor-pointer"
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
