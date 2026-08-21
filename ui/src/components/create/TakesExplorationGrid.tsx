import { Play, Loader2 } from 'lucide-react';

interface TakeItem {
  id: number;
  seed: number;
  video_url: string;
  pan_deg?: number;
}

interface TakesExplorationGridProps {
  takes?: TakeItem[];
  isGenerating?: boolean;
}

export function TakesExplorationGrid({ takes, isGenerating }: TakesExplorationGridProps) {
  const fallbackSeeds = [482910, 482911, 482912, 482913];

  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm">
      <div className="flex justify-between items-center">
        <h2 className="text-[13px] font-semibold text-white/60 uppercase tracking-wider">4-Take Exploration Grid</h2>
        <span className="text-[11px] font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded border border-emerald-400/20">
          {takes && takes.length > 0 ? `${takes.length} Active Takes` : 'Batch Seeds: +1 Step'}
        </span>
      </div>

      {isGenerating && (
        <div className="flex items-center justify-center p-8 bg-black/40 border border-white/[0.08] rounded-lg gap-3 text-sm text-white/70">
          <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
          <span>GPU inference running... Rendering multi-take grid.</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {takes && takes.length > 0 ? (
          takes.map((take) => (
            <div key={take.id} className="relative aspect-video bg-[#111114] rounded-lg border border-white/[0.14] overflow-hidden group hover:border-emerald-500/50 transition-colors">
              <video 
                src={take.video_url} 
                className="w-full h-full object-cover" 
                controls 
                autoPlay 
                loop 
                muted 
              />
              <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/80 font-mono text-[10px] text-white/80 border border-white/10">
                Take #{take.id} · Seed {take.seed}
              </div>
            </div>
          ))
        ) : (
          fallbackSeeds.map((seed, idx) => (
            <div key={seed} className="relative aspect-video bg-[#111114] rounded-lg border border-white/[0.08] overflow-hidden group hover:border-amber-500/50 transition-colors cursor-pointer">
              <div className="absolute inset-0 flex flex-col items-center justify-center text-white/20 gap-1">
                <Play className="w-6 h-6" />
                <span className="font-mono text-[10px]">Take #{idx + 1} Placeholder</span>
              </div>
              
              <div className="absolute bottom-0 left-0 right-0 p-2.5 bg-gradient-to-t from-black/90 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex justify-between items-center">
                <span className="text-[10px] font-mono text-white/70">Seed: {seed}</span>
                <button 
                  onClick={() => {
                    alert(`Seed ${seed} selected for director prompt.`);
                  }}
                  className="px-2 py-1 bg-white/10 hover:bg-amber-500 hover:text-black text-white text-[10px] font-bold rounded backdrop-blur-md transition-colors cursor-pointer"
                >
                  Select Seed
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
