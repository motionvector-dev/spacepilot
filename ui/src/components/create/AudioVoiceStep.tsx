import { useState } from 'react';

export function AudioVoiceStep() {
  const [ducking, setDucking] = useState(true);

  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl hover:bg-[#111114] transition-colors">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-white/60"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
          <h2 className="text-[13px] font-semibold text-white/60 uppercase tracking-wider">Audio & Voiceover</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-white/40 bg-black px-1.5 py-0.5 rounded border border-white/[0.08]">Sidechain: -16.0 LUFS</span>
          <button 
            onClick={() => setDucking(!ducking)}
            className={`w-8 h-4 rounded-full p-0.5 transition-colors focus:outline-none ${ducking ? 'bg-emerald-500' : 'bg-[#222226]'}`}
          >
            <div className={`w-3 h-3 rounded-full bg-white shadow-sm transition-transform ${ducking ? 'translate-x-4' : 'translate-x-0'}`} />
          </button>
        </div>
      </div>

      <div className="flex gap-4">
        <div className="flex-1 flex flex-col gap-2">
          <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Kokoro Profile</label>
          <div className="relative">
            <select className="w-full appearance-none bg-black border border-white/[0.14] rounded-md px-3 py-2 text-[13px] font-medium text-white focus:outline-none focus:border-white/30 cursor-pointer">
              <option value="af_bella">Bella (Expressive Female)</option>
              <option value="am_adam">Adam (Deep Male)</option>
              <option value="af_heart">Heart (Warm Female)</option>
            </select>
            <div className="absolute right-3 top-[10px] pointer-events-none text-white/30">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </div>
          </div>
        </div>

        <div className="flex-[2] flex flex-col gap-2">
          <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Dialogue Script</label>
          <input 
            type="text" 
            className="w-full bg-black border border-white/[0.14] rounded-md px-3 py-2 text-[13px] text-white focus:outline-none focus:border-white/30 placeholder-white/30"
            placeholder="Type narration here to synthesize... (auto-ducked over BGM)"
          />
        </div>
      </div>

      {/* Waveform Meter Fake */}
      <div className="flex items-end gap-[2px] h-10 p-2 bg-black border border-white/[0.08] rounded-md overflow-hidden opacity-80">
        {Array.from({length: 60}).map((_, i) => (
          <div 
            key={i} 
            className="flex-1 bg-emerald-500/60 rounded-t-[1px]"
            style={{ height: `${Math.max(15, Math.random() * 100)}%` }}
          />
        ))}
      </div>
    </div>
  );
}
