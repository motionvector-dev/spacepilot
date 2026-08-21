import React, { useState } from 'react';

export const CenterStagePromptHero: React.FC = () => {
  const [prompt, setPrompt] = useState('');

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black overflow-hidden pt-[44px] pl-[56px] pr-[320px]">
      {/* Dynamic Background subtle grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)]" />

      <div className="relative w-full max-w-3xl px-6 z-10 flex flex-col items-center">
        <div className="mb-8 text-center space-y-4">
          <h2 className="text-4xl md:text-5xl font-geist font-bold tracking-tight text-white/90">
            What will you create?
          </h2>
          <p className="text-white/40 text-sm md:text-base max-w-lg mx-auto">
            Describe your vision, drop an image, or use a skill command like <code className="text-emerald-400 bg-emerald-400/10 px-1 py-0.5 rounded">/T2V</code>.
          </p>
        </div>

        <div className="w-full relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-emerald-500/30 via-cyan-500/30 to-purple-500/30 rounded-2xl blur opacity-30 group-hover:opacity-60 transition duration-500" />
          
          <div className="relative flex flex-col w-full bg-[#111114] border border-white/10 rounded-2xl shadow-2xl overflow-hidden transition-all duration-300 focus-within:border-white/20 focus-within:shadow-[0_0_30px_rgba(255,255,255,0.05)]">
            <div className="flex items-start p-4 pb-2">
              <button className="mt-1 flex-shrink-0 w-8 h-8 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 flex items-center justify-center text-white/60 transition-colors">
                <span className="w-4 h-4 i-lucide-plus" />
              </button>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="A cinematic tracking shot of..."
                className="flex-1 ml-3 bg-transparent text-white/90 placeholder:text-white/30 resize-none outline-none min-h-[80px] text-lg font-geist leading-relaxed scrollbar-hide py-1"
                autoFocus
              />
            </div>
            
            <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-t border-white/5">
              <div className="flex items-center gap-2">
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 text-xs text-white/70 transition-colors">
                  <span className="w-3.5 h-3.5 i-lucide-settings-2" />
                  Ask · Quality
                </button>
                <div className="text-xs text-white/30 hidden sm:flex items-center gap-1 font-mono">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-white/10 border border-white/20 text-white/50">Tab</kbd> to autocomplete
                </div>
              </div>
              
              <button 
                className={`flex items-center justify-center w-8 h-8 rounded-full transition-all duration-300 ${
                  prompt.trim().length > 0 
                    ? 'bg-white text-black hover:scale-105' 
                    : 'bg-white/10 text-white/30 cursor-not-allowed'
                }`}
              >
                <span className="w-4 h-4 i-lucide-arrow-right" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
