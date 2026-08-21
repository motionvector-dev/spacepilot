import { useState } from 'react';
import { useSynthesizeAudio } from '../../hooks/useGenerate';
import { Mic, Loader2, Play, Check } from 'lucide-react';

export function AudioVoiceStep() {
  const [ducking, setDucking] = useState(true);
  const [voice, setVoice] = useState('af_bella');
  const [dialogue, setDialogue] = useState('');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const synthMutation = useSynthesizeAudio();

  const handleSynthesize = async () => {
    if (!dialogue.trim()) return;
    try {
      const res = await synthMutation.mutateAsync({
        text: dialogue,
        voice,
        target_lufs: -16.0,
      });
      if (res.audio_url) {
        setAudioUrl(res.audio_url);
      }
    } catch {
      // Handled by synthMutation.isError
    }
  };

  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl hover:bg-[#111114] transition-colors">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Mic className="w-4 h-4 text-white/60" />
          <h2 className="text-[13px] font-semibold text-white/60 uppercase tracking-wider">Audio & Voiceover</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-white/40 bg-black px-1.5 py-0.5 rounded border border-white/[0.08]">Sidechain: -16.0 LUFS</span>
          <button 
            onClick={() => setDucking(!ducking)}
            className={`w-8 h-4 rounded-full p-0.5 transition-colors focus:outline-none cursor-pointer ${ducking ? 'bg-emerald-500' : 'bg-[#222226]'}`}
          >
            <div className={`w-3 h-3 rounded-full bg-white shadow-sm transition-transform ${ducking ? 'translate-x-4' : 'translate-x-0'}`} />
          </button>
        </div>
      </div>

      <div className="flex gap-4">
        <div className="flex-1 flex flex-col gap-2">
          <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Kokoro Profile</label>
          <div className="relative">
            <select 
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              className="w-full appearance-none bg-black border border-white/[0.14] rounded-md px-3 py-2 text-[13px] font-medium text-white focus:outline-none focus:border-white/30 cursor-pointer"
            >
              <option value="af_bella">Bella (Expressive Female)</option>
              <option value="am_adam">Adam (Deep Male)</option>
              <option value="af_heart">Heart (Warm Female)</option>
              <option value="bf_alice">Alice (British Female)</option>
            </select>
            <div className="absolute right-3 top-[10px] pointer-events-none text-white/30">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </div>
          </div>
        </div>

        <div className="flex-[2] flex flex-col gap-2">
          <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Dialogue Script</label>
          <div className="flex gap-2">
            <input 
              type="text" 
              value={dialogue}
              onChange={(e) => setDialogue(e.target.value)}
              className="flex-1 bg-black border border-white/[0.14] rounded-md px-3 py-2 text-[13px] text-white focus:outline-none focus:border-white/30 placeholder-white/30"
              placeholder="Type narration here to synthesize... (auto-ducked over BGM)"
            />
            <button
              onClick={handleSynthesize}
              disabled={synthMutation.isPending || !dialogue.trim()}
              className="px-3 py-2 bg-[#18181b] hover:bg-[#222226] border border-white/[0.14] rounded-md text-xs font-semibold text-white/80 hover:text-white transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {synthMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              <span>Synth</span>
            </button>
          </div>
        </div>
      </div>

      {audioUrl && (
        <div className="flex items-center justify-between p-3 bg-black/60 border border-emerald-500/30 rounded-lg">
          <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono">
            <Check className="w-4 h-4 text-emerald-400" />
            <span>Kokoro Audio Synthesized (-16.0 LUFS)</span>
          </div>
          <audio controls src={audioUrl} className="h-7 max-w-[200px]" />
        </div>
      )}
    </div>
  );
}
