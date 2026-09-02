import { useState, useRef, useEffect } from 'react';
import type { KeyboardEvent, ChangeEvent } from 'react';
import { 
  Plus, 
  ArrowRight, 
  Sparkles, 
  SlidersHorizontal, 
  Loader2, 
  X, 
  Play, 
  Film, 
  Flame, 
  Atom, 
  Cpu, 
  Waves
} from 'lucide-react';
import { useStudioStore } from '../../../stores/studioStore';
import { useGenerateVideo } from '../../../hooks/useGenerate';

const PROMPT_SUGGESTIONS = [
  'Establishing wide dolly-in: Cyberpunk neon alleyway with volumetric rain and anamorphic reflections',
  'Diffusion physics: Continuous velocity vector fields flowing on a 3D Riemannian manifold',
  'Visualizing Transformer Attention Matrices & Residual Streams in 3D holographic wireframe',
  'Quantum Entanglement wavefunction collapse in 4K photorealistic glass chamber',
  'High-speed macro lens tracking of molten glass fluid dynamics with chromatic dispersion',
];

const INSPIRATION_CHIPS = [
  { id: 'diff', label: 'AI Diffusion Physics', icon: Flame, prompt: 'Continuous velocity vector field flow of diffusion reverse process, particles coalescing into photorealistic 4k scene' },
  { id: 'quantum', label: 'Quantum Superposition', icon: Atom, prompt: 'Visualizing quantum superposition state and wave-function collapse in complex Hilbert space, glowing iridescent vectors' },
  { id: 'attn', label: 'Transformer Attention', icon: Cpu, prompt: 'Holographic 3D multi-head attention matrix heatmaps flowing through transformer residual streams' },
  { id: 'fluid', label: 'Fluid Dynamics', icon: Waves, prompt: 'Extreme slow-motion fluid dynamics simulation with Navier-Stokes velocity vectors and surface tension' },
];

export const CenterStagePromptHero = () => {
  const { 
    prompt, 
    setPrompt, 
    setActiveSkill,
    attachedImage, 
    setAttachedImage,
    generationPreferences, 
    setGenerationPreferences,
    isGenerating, 
    setIsGenerating,
    setLastGeneratedJobId,
    addChatMessage,
    takes,
    selectedTakeId,
    setSelectedTakeId,
    panAngle,
    zoomRatio
  } = useStudioStore();

  const [suggestionIdx, setSuggestionIdx] = useState(0);
  const [showPrefsPopover, setShowPrefsPopover] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const generateMutation = useGenerateVideo();

  // Rotate suggestion periodically if prompt is empty
  useEffect(() => {
    const interval = setInterval(() => {
      setSuggestionIdx((prev) => (prev + 1) % PROMPT_SUGGESTIONS.length);
    }, 6000);
    return () => clearInterval(interval);
  }, []);

  const currentSuggestion = PROMPT_SUGGESTIONS[suggestionIdx];

  const handleTabCompletion = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab' && (!prompt || prompt.trim().length === 0)) {
      e.preventDefault();
      setPrompt(currentSuggestion);
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleImageUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    setAttachedImage({
      name: file.name,
      url,
      file,
    });
    setActiveSkill('i2v');
  };

  const handleSubmit = async () => {
    const cleanPrompt = prompt.trim() || currentSuggestion;
    if (!cleanPrompt || isGenerating) return;

    setGenerationError(null);
    setIsGenerating(true);

    // Add user message to conversation history
    addChatMessage({
      role: 'user',
      text: cleanPrompt,
    });

    try {
      const res = await generateMutation.mutateAsync({
        prompt: cleanPrompt,
        engine: generationPreferences.engine,
        seconds: generationPreferences.duration,
        camera_pan: `+${panAngle}deg`,
        camera_zoom: `${zoomRatio}x`,
        enhance: generationPreferences.enhance,
        image_path: attachedImage?.url || null,
      });

      setLastGeneratedJobId(res.job_id);

      // Add agent response
      addChatMessage({
        role: 'agent',
        text: `Generation job launched successfully (ID: ${res.job_id.slice(0, 8)}...). Synthesizing frames on AWS L40S spot GPU.`,
        reasoning: `> Engine: ${generationPreferences.engine}\n> Target: ${generationPreferences.target}\n> Resolution: 1920x1080 @ 24fps\n> Camera guidance: Pan ${panAngle}°, Zoom ${zoomRatio}x`,
        tags: [generationPreferences.engine, `${generationPreferences.duration}s`, generationPreferences.target],
      });
    } catch (err: any) {
      console.error('Generation error:', err);
      setGenerationError(err?.message || 'Generation failed. Spot GPU offline or mock fallback active.');
      // Add simulated agent reply for offline/mock mode
      addChatMessage({
        role: 'agent',
        text: `Simulating render pipeline for: "${cleanPrompt.slice(0, 45)}..." on local fallback daemon.`,
        reasoning: `> Applied STG motion guidance: ${panAngle}°\n> Resolution target: 1080p ProRes 422\n> Ready for playback in cinema viewport`,
        tags: ['Simulation', 'Mock GPU', 'ProRes 422'],
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-start bg-black overflow-y-auto pt-[60px] pb-32 pl-[56px] pr-[320px] scrollbar-hide select-none">
      {/* Background Subtle Radial Gradient Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800c_1px,transparent_1px),linear-gradient(to_bottom,#8080800c_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="relative w-full max-w-3xl px-6 z-10 flex flex-col items-center mt-4">
        {/* Hero Title & Subtitle */}
        <div className="mb-6 text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-white/70 font-mono mb-2">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>MotionVector Gen-4 · Agent-First Creative Suite</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white font-sans">
            What do you want to create?
          </h2>
          <p className="text-white/40 text-xs md:text-sm max-w-md mx-auto">
            Describe your vision, attach reference frames, or invoke skills with <code className="text-emerald-400 bg-emerald-400/10 px-1 py-0.5 rounded font-mono">/T2V</code> or <code className="text-cyan-400 bg-cyan-400/10 px-1 py-0.5 rounded font-mono">/I2V</code>.
          </p>
        </div>

        {/* Universal Floating Prompt Input Card */}
        <div className="w-full relative group">
          <div className={`absolute -inset-0.5 bg-gradient-to-r from-emerald-500/30 via-cyan-500/30 to-purple-500/30 rounded-2xl blur opacity-30 transition duration-500 ${
            isGenerating ? 'opacity-90 animate-pulse' : 'group-hover:opacity-60'
          }`} />

          <div className="relative flex flex-col w-full bg-[#111114] border border-white/10 rounded-2xl shadow-2xl overflow-hidden transition-all duration-300 focus-within:border-white/25 focus-within:shadow-[0_0_30px_rgba(255,255,255,0.06)]">
            
            {/* Attached Media Thumbnail Bar */}
            {attachedImage && (
              <div className="flex items-center gap-2 px-4 pt-3 pb-1 border-b border-white/5 bg-black/40">
                <div className="relative group/thumb flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg p-1 pr-2">
                  <img 
                    src={attachedImage.url} 
                    alt={attachedImage.name} 
                    className="w-8 h-8 rounded object-cover border border-white/10"
                  />
                  <div className="flex flex-col text-left">
                    <span className="text-[11px] font-medium text-white/90 truncate max-w-[140px]">
                      {attachedImage.name}
                    </span>
                    <span className="text-[9px] font-mono text-emerald-400">First Frame Keyframe</span>
                  </div>
                  <button
                    onClick={() => setAttachedImage(null)}
                    className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-white cursor-pointer ml-1"
                    title="Remove attached image"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              </div>
            )}

            {/* Prompt Textarea */}
            <div className="flex items-start p-4 pb-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="mt-1 flex-shrink-0 w-8 h-8 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors cursor-pointer"
                title="Attach Keyframe Image (/I2V)"
              >
                <Plus className="w-4 h-4" />
              </button>
              
              <div className="relative flex-1 ml-3">
                <textarea
                  ref={textareaRef}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={handleTabCompletion}
                  placeholder={currentSuggestion}
                  rows={3}
                  className="w-full bg-transparent text-white/95 placeholder:text-white/25 resize-none outline-none text-base font-sans leading-relaxed scrollbar-hide py-1"
                  autoFocus
                />
              </div>
            </div>

            {/* Prompt Bottom Action Bar */}
            <div className="flex items-center justify-between px-4 py-3 bg-white/[0.03] border-t border-white/5 relative">
              <div className="flex items-center gap-2">
                {/* Generation Preferences Button ("Ask · Quality") */}
                <div className="relative">
                  <button
                    onClick={() => setShowPrefsPopover(!showPrefsPopover)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
                      showPrefsPopover
                        ? 'bg-white/15 text-white border-white/30'
                        : 'bg-white/5 hover:bg-white/10 border-white/10 text-white/70 hover:text-white'
                    }`}
                  >
                    <SlidersHorizontal className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{generationPreferences.mode === 'ask' ? 'Ask' : 'Auto'} · {generationPreferences.target.toUpperCase()}</span>
                  </button>

                  {/* Preferences Popover Modal */}
                  {showPrefsPopover && (
                    <div 
                      className="absolute left-0 bottom-full mb-2 w-72 bg-[#18181b] border border-white/15 rounded-xl shadow-2xl p-4 z-50 text-xs font-sans space-y-3"
                      onMouseLeave={() => setShowPrefsPopover(false)}
                    >
                      <div className="flex justify-between items-center pb-2 border-b border-white/10">
                        <span className="font-bold text-white">Generation Preferences</span>
                        <span className="text-[10px] font-mono text-emerald-400">L40S 48GB</span>
                      </div>

                      {/* Ask vs Auto */}
                      <div>
                        <span className="text-[10px] font-mono text-white/50 block mb-1">When generating media</span>
                        <div className="grid grid-cols-2 gap-1.5 font-mono">
                          <button
                            onClick={() => setGenerationPreferences({ mode: 'ask' })}
                            className={`py-1 rounded border text-center cursor-pointer transition-all ${
                              generationPreferences.mode === 'ask'
                                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 font-bold'
                                : 'bg-black/40 text-white/50 border-white/5'
                            }`}
                          >
                            Ask (Confirm)
                          </button>
                          <button
                            onClick={() => setGenerationPreferences({ mode: 'auto' })}
                            className={`py-1 rounded border text-center cursor-pointer transition-all ${
                              generationPreferences.mode === 'auto'
                                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 font-bold'
                                : 'bg-black/40 text-white/50 border-white/5'
                            }`}
                          >
                            Auto (Instant)
                          </button>
                        </div>
                      </div>

                      {/* Optimize Target */}
                      <div>
                        <span className="text-[10px] font-mono text-white/50 block mb-1">Optimize generations</span>
                        <div className="grid grid-cols-4 gap-1 font-mono text-[10px]">
                          {(['quality', 'speed', 'cost', 'custom'] as const).map((tgt) => (
                            <button
                              key={tgt}
                              onClick={() => setGenerationPreferences({ target: tgt })}
                              className={`py-1 rounded border text-center capitalize cursor-pointer transition-all ${
                                generationPreferences.target === tgt
                                  ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40 font-bold'
                                  : 'bg-black/40 text-white/50 border-white/5'
                              }`}
                            >
                              {tgt}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Duration */}
                      <div>
                        <span className="text-[10px] font-mono text-white/50 block mb-1">Duration & Aspect</span>
                        <div className="grid grid-cols-3 gap-1 font-mono text-[10px]">
                          {[4, 8, 16].map((sec) => (
                            <button
                              key={sec}
                              onClick={() => setGenerationPreferences({ duration: sec })}
                              className={`py-1 rounded border text-center cursor-pointer transition-all ${
                                generationPreferences.duration === sec
                                  ? 'bg-white/20 text-white border-white/40 font-bold'
                                  : 'bg-black/40 text-white/50 border-white/5'
                              }`}
                            >
                              {sec}s
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Tab to Autocomplete Cue */}
                {(!prompt || prompt.length === 0) && (
                  <div className="text-[11px] text-white/40 hidden sm:flex items-center gap-1 font-mono">
                    Press <kbd className="px-1.5 py-0.5 rounded bg-white/10 border border-white/20 text-white/70 text-[10px]">Tab</kbd> to complete
                  </div>
                )}
              </div>

              {/* Submit / Generate Button */}
              <button 
                onClick={handleSubmit}
                disabled={isGenerating}
                className={`flex items-center justify-center h-8 px-3.5 rounded-full transition-all duration-300 gap-1.5 cursor-pointer font-medium text-xs ${
                  isGenerating 
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : prompt.trim().length > 0 || currentSuggestion
                    ? 'bg-white text-black hover:bg-white/90 hover:scale-105 shadow-md' 
                    : 'bg-white/10 text-white/30 cursor-not-allowed'
                }`}
                title="Generate Video (Enter)"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Synthesizing...</span>
                  </>
                ) : (
                  <>
                    <span>Generate</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Generation Status & Error Bar */}
        {generationError && (
          <div className="w-full mt-3 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-mono flex items-center justify-between">
            <span>{generationError}</span>
            <button onClick={() => setGenerationError(null)} className="text-amber-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Quick Creative Inspiration Chips */}
        <div className="w-full mt-6">
          <div className="flex items-center gap-2 mb-2 px-1">
            <span className="text-[11px] font-mono text-white/40 uppercase tracking-wider">
              Creative Inspirations:
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {INSPIRATION_CHIPS.map((chip) => {
              const Icon = chip.icon;
              return (
                <button
                  key={chip.id}
                  onClick={() => setPrompt(chip.prompt)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#18181b]/80 hover:bg-[#222226] border border-white/10 hover:border-white/20 text-xs text-white/70 hover:text-white transition-all cursor-pointer group"
                >
                  <Icon className="w-3.5 h-3.5 text-emerald-400 group-hover:scale-110 transition-transform" />
                  <span>{chip.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Active Takes Reel Preview Card */}
        <div className="w-full mt-8 bg-[#111114] border border-white/10 rounded-xl p-4 shadow-xl">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center gap-2 font-mono text-xs">
              <Film className="w-4 h-4 text-emerald-400" />
              <span className="font-bold text-white">Audition Takes Bin</span>
              <span className="text-white/40">({takes.length} Takes)</span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              LTX-2.5 48GB Ready
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            {takes.map((take) => (
              <div
                key={take.id}
                onClick={() => setSelectedTakeId(take.id)}
                className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col gap-2 ${
                  selectedTakeId === take.id
                    ? 'bg-[#18181b] border-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
                    : 'bg-black/40 border-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="font-bold text-white">Take #{take.id}</span>
                  <span className="text-emerald-400 text-[10px]">SEED {take.seed}</span>
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono text-white/50">
                  <span>Pan: +{take.panDeg}°</span>
                  <span>Zoom: {take.zoomRatio}x</span>
                </div>
                <div className="flex items-center justify-center h-12 bg-black/60 rounded border border-white/5 text-white/40 group hover:text-white">
                  <Play className="w-5 h-5 fill-current" />
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
};

export default CenterStagePromptHero;
