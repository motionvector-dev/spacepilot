import React from 'react';

export const TopMiniHeader: React.FC = () => {
  return (
    <header className="fixed top-0 left-[56px] right-0 h-[44px] bg-[#09090b]/80 backdrop-blur-md border-b border-white/10 flex items-center justify-between px-4 z-30">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-medium text-white/90 font-geist">
          Project Alpha
        </h1>
        <span className="text-xs text-white/40 px-2 py-0.5 rounded-full bg-white/5 border border-white/10 font-mono">
          Chat #829
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          $0.14 / GPU hr
        </div>
        
        <button className="h-7 px-3 rounded-md bg-white text-black text-xs font-semibold hover:bg-white/90 transition-colors flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 i-lucide-rocket" />
          Launch GPU
        </button>

        <div className="w-px h-4 bg-white/10 mx-1" />

        <button className="w-7 h-7 flex items-center justify-center rounded hover:bg-white/10 text-white/60 hover:text-white transition-colors">
          <span className="w-4 h-4 i-lucide-more-horizontal" />
        </button>
      </div>
    </header>
  );
};
