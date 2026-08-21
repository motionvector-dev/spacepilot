import { useEnhancePrompt } from '../../hooks/useGenerate';
import { Sparkles, Loader2 } from 'lucide-react';

interface PromptScriptStepProps {
  prompt: string;
  setPrompt: (p: string) => void;
  aspect: string;
  setAspect: (a: string) => void;
  cameraTags: string[];
  setCameraTags: (tags: string[]) => void;
}

export function PromptScriptStep({
  prompt,
  setPrompt,
  aspect,
  setAspect,
  cameraTags,
  setCameraTags,
}: PromptScriptStepProps) {
  const enhanceMutation = useEnhancePrompt();

  const handleEnhance = async () => {
    if (!prompt.trim()) return;
    try {
      const res = await enhanceMutation.mutateAsync(prompt);
      if (res.enhanced_prompt) {
        setPrompt(res.enhanced_prompt);
      }
    } catch {
      // Fallback local enhancement if backend enhance-prompt is offline
      setPrompt(`${prompt}, cinematic lighting, photorealistic, 8k resolution, highly detailed, atmospheric haze, 35mm photograph`);
    }
  };

  const toggleTag = (tag: string) => {
    if (cameraTags.includes(tag)) {
      setCameraTags(cameraTags.filter(t => t !== tag));
    } else {
      setCameraTags([...cameraTags, tag]);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm hover:border-white/[0.14] transition-colors">
      <div className="flex justify-between items-center">
        <h2 className="text-[13px] font-semibold text-white/60 uppercase tracking-wider">Prompt Definition</h2>
        <button 
          onClick={handleEnhance}
          disabled={enhanceMutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#18181b] border border-white/[0.14] text-xs font-semibold text-white/80 hover:text-white hover:border-white/30 hover:bg-[#222226] transition-all cursor-pointer disabled:opacity-50"
        >
          {enhanceMutation.isPending ? (
            <Loader2 className="w-3 h-3 animate-spin text-purple-400" />
          ) : (
            <Sparkles className="w-3 h-3 text-purple-400" />
          )}
          <span>{enhanceMutation.isPending ? 'Enhancing...' : 'Enhance'}</span>
        </button>
      </div>

      <textarea 
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        className="w-full h-32 p-3.5 bg-black border border-white/[0.14] rounded-lg text-[15px] text-white focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 transition-all resize-y placeholder-white/30 leading-relaxed font-sans"
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
                  className={`px-3 py-1 text-xs font-semibold rounded transition-colors cursor-pointer ${aspect === a ? 'bg-[#18181b] text-white border-white/[0.08] shadow-sm' : 'text-white/40 hover:text-white/80 hover:bg-[#111114]'}`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Camera Motion</span>
            <div className="flex gap-2">
              {['Pan Right', 'Dolly In', 'Tilt Up', 'Roll 360'].map(tag => {
                const isActive = cameraTags.includes(tag);
                return (
                  <button 
                    key={tag} 
                    onClick={() => toggleTag(tag)}
                    className={`px-2 py-1 rounded border text-[11px] font-mono transition-all cursor-pointer ${
                      isActive 
                        ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400' 
                        : 'bg-[#111114] border-white/[0.08] text-white/40 hover:text-white/70'
                    }`}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="text-[12px] font-mono text-white/40">
          {prompt.length} / 4000
        </div>
      </div>
    </div>
  );
}
