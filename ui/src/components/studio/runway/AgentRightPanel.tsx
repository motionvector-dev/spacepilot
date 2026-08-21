import React, { useState } from 'react';

export const AgentRightPanel: React.FC = () => {
  const [isReasoningExpanded, setIsReasoningExpanded] = useState(false);

  return (
    <aside className="fixed right-0 top-0 bottom-0 w-[320px] bg-[#09090b] border-l border-white/10 z-30 flex flex-col pt-[44px]">
      <div className="flex-1 overflow-y-auto scrollbar-hide p-4 space-y-6">
        
        {/* User Message */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30">
              <span className="text-blue-400 text-[10px] font-bold i-lucide-user w-3 h-3" />
            </div>
            <span className="text-xs font-medium text-white/70">You</span>
          </div>
          <div className="bg-white/5 border border-white/10 rounded-lg p-3 text-sm text-white/90 font-geist">
            I want a slow pan across a futuristic neon city, raining heavily.
          </div>
        </div>

        {/* Agent Response */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
              <span className="text-emerald-400 text-[10px] font-bold i-lucide-bot w-3 h-3" />
            </div>
            <span className="text-xs font-medium text-white/70">Director Agent</span>
          </div>
          
          <div className="bg-[#111114] border border-white/10 rounded-lg p-3 text-sm text-white/90 space-y-3 font-geist">
            <p>I've configured the scene for a classic cyberpunk atmosphere. Let's adjust the parameters for the best result.</p>
            
            {/* Reasoning Expander */}
            <div className="border border-white/5 rounded-md overflow-hidden bg-black/50">
              <button 
                onClick={() => setIsReasoningExpanded(!isReasoningExpanded)}
                className="flex items-center justify-between w-full p-2 text-xs text-white/60 hover:text-white/80 transition-colors bg-white/5"
              >
                <div className="flex items-center gap-2">
                  <span className="w-3.5 h-3.5 i-lucide-cpu text-purple-400" />
                  <span>Model Reasoning</span>
                </div>
                <span className={`w-3.5 h-3.5 transition-transform ${isReasoningExpanded ? 'rotate-180' : ''} i-lucide-chevron-down`} />
              </button>
              {isReasoningExpanded && (
                <div className="p-2.5 text-xs text-white/50 font-mono leading-relaxed border-t border-white/5">
                  &gt; Analyzed prompt: "slow pan", "neon city", "raining"<br/>
                  &gt; Added structural keywords: "cinematic lighting", "8k resolution"<br/>
                  &gt; Camera motion set to: Pan Right (speed: 2)<br/>
                  &gt; Style alignment: Cyberpunk / Sci-Fi
                </div>
              )}
            </div>

            {/* Prompt Breakdown */}
            <div className="space-y-2 pt-2 border-t border-white/10">
              <div className="text-xs font-medium text-white/60">Enhanced Prompt</div>
              <div className="flex flex-wrap gap-1.5">
                <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] border border-emerald-500/20">slow pan right</span>
                <span className="px-1.5 py-0.5 rounded bg-white/10 text-white/70 text-[10px] border border-white/10">futuristic neon city</span>
                <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[10px] border border-cyan-500/20">heavy rain</span>
                <span className="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 text-[10px] border border-purple-500/20">cinematic lighting</span>
                <span className="px-1.5 py-0.5 rounded bg-white/10 text-white/70 text-[10px] border border-white/10">8k resolution</span>
              </div>
            </div>

            {/* Parameter Sliders */}
            <div className="space-y-3 pt-3 border-t border-white/10">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-white/60">Motion Amount</span>
                  <span className="text-white/90 font-mono">60</span>
                </div>
                <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 w-[60%]" />
                </div>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-white/60">Guidance Scale</span>
                  <span className="text-white/90 font-mono">7.5</span>
                </div>
                <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-cyan-500 w-[75%]" />
                </div>
              </div>
            </div>
            
          </div>
        </div>
        
      </div>
      
      {/* Input Area */}
      <div className="p-4 border-t border-white/10 bg-[#09090b]">
        <div className="relative flex items-center bg-[#111114] border border-white/10 rounded-lg focus-within:border-white/20 transition-colors">
          <input 
            type="text" 
            placeholder="Adjust params or reply..." 
            className="w-full bg-transparent text-sm text-white/90 placeholder:text-white/30 outline-none py-2.5 pl-3 pr-10 font-geist"
          />
          <button className="absolute right-2 w-7 h-7 flex items-center justify-center rounded text-white/40 hover:text-white hover:bg-white/10 transition-colors">
            <span className="w-4 h-4 i-lucide-send" />
          </button>
        </div>
      </div>
    </aside>
  );
};
