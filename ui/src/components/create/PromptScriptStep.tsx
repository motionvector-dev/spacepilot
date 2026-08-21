import { useState } from 'react';

export function PromptScriptStep() {
  const [aspect, setAspect] = useState('16:9');
  
  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm hover:border-white/[0.14] transition-colors">
      <div className="flex justify-between items-center">
        <h2 className="text-[13px] font-semibold text-white/60 uppercase tracking-wider">Prompt Definition</h2>
        <button className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#18181b] border border-white/[0.14] text-xs font-semibold text-white/60 hover:text-white hover:border-white/30 hover:bg-[#222226] transition-all">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          Enhance
        </button>
      </div>

      <textarea 
        className="w-full h-32 p-3.5 bg-black border border-white/[0.14] rounded-lg text-[15px] text-white focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 transition-all resize-y placeholder-white/30 leading-relaxed"
        placeholder="Describe the scene with rich visual details... (e.g. Cinematic wide tracking shot of a futuristic motorcycle accelerating through neon-lit rain-slicked Tokyo streets at midnight, 35mm lens, atmospheric haze)"
      />

      <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
        <div className="flex items-center gap-4">
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Aspect Ratio</span>
            <div className="flex bg-black p-0.5 rounded-md border border-white/[0.08]">
              {['16:9', '9:16', '1:1', '2.35:1'].map(a => (
                <button 
                  key={a}
                  onClick={() => setAspect(a)}
                  className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${aspect === a ? 'bg-[#18181b] text-white border-white/[0.08] shadow-sm' : 'text-white/40 hover:text-white/80 hover:bg-[#111114]'}`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Camera Motion</span>
            <div className="flex gap-2">
              {['Pan Right', 'Dolly In'].map(tag => (
                <span key={tag} className="px-2 py-1 rounded bg-[#111114] border border-white/[0.08] text-[11px] font-mono text-cyan-400">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="text-[12px] font-mono text-white/40">
          0 / 4000
        </div>
      </div>
    </div>
  );
}
