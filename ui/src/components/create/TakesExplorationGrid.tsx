

export function TakesExplorationGrid() {
  const seeds = [482910, 482911, 482912, 482913];

  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm">
      <div className="flex justify-between items-center">
        <h2 className="text-[13px] font-semibold text-white/60 uppercase tracking-wider">4-Take Exploration Grid</h2>
        <span className="text-[11px] font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded border border-emerald-400/20">
          Batch Seeds: +1 Step
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {seeds.map((seed) => (
          <div key={seed} className="relative aspect-video bg-[#111114] rounded-lg border border-white/[0.08] overflow-hidden group hover:border-amber-500/50 transition-colors cursor-pointer">
            <div className="absolute inset-0 flex items-center justify-center text-white/10">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
            </div>
            
            <div className="absolute bottom-0 left-0 right-0 p-2.5 bg-gradient-to-t from-black/90 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex justify-between items-center">
              <span className="text-[10px] font-mono text-white/70">Seed: {seed}</span>
              <button className="px-2 py-1 bg-white/10 hover:bg-amber-500 hover:text-black text-white text-[10px] font-bold rounded backdrop-blur-md transition-colors">
                Upscale
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
