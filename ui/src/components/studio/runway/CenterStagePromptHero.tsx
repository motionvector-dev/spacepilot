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
    <div className="absolute inset-0 flex flex-col items-center justify-start bg-ground overflow-y-auto pt-[60px] pb-32 pl-[56px] pr-[320px] scrollbar-hide select-none">
      {/* Background Subtle Radial Gradient Grid — already a neutral gray hairline, not one of the mapped hues */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800c_1px,transparent_1px),linear-gradient(to_bottom,#8080800c_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="relative w-full max-w-3xl px-6 z-10 flex flex-col items-center mt-4">
        {/* Hero Title & Subtitle */}
        <div className="mb-6 text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-inset border border-line-200 text-xs text-ink-700 font-mono mb-2">
            <Sparkles className="w-3.5 h-3.5 text-verify" />
            <span>MotionVector Gen-4 · Agent-First Creative Suite</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-ink font-sans">
            What do you want to create?
          </h2>
          <p className="text-ink-500 text-xs md:text-sm max-w-md mx-auto">
            Describe your vision, attach reference frames, or invoke skills with <code className="text-verify bg-verify-soft px-1 py-0.5 rounded font-mono">/T2V</code> or <code className="text-ink-900 bg-inset px-1 py-0.5 rounded font-mono">/I2V</code>.
          </p>
        </div>

        {/* Universal Floating Prompt Input Card */}
        <div className="w-full relative group">
          <div className="relative flex flex-col w-full bg-raised border border-line-200 rounded-2xl overflow-hidden transition-all duration-300 focus-within:border-line-400">

            {/* Attached Media Thumbnail Bar */}
            {attachedImage && (
              <div className="flex items-center gap-2 px-4 pt-3 pb-1 border-b border-line-100 bg-ground/40">
                <div className="relative group/thumb flex items-center gap-2 bg-inset border border-line-200 rounded-lg p-1 pr-2">
                  <img
                    src={attachedImage.url}
                    alt={attachedImage.name}
                    className="w-8 h-8 rounded object-cover border border-line-200"
                  />
                  <div className="flex flex-col text-left">
                    <span className="text-[11px] font-medium text-ink-900 truncate max-w-[140px]">
                      {attachedImage.name}
                    </span>
                    <span className="text-[9px] font-mono text-verify">First Frame Keyframe</span>
                  </div>
                  <button
                    onClick={() => setAttachedImage(null)}
                    className="p-1 rounded hover:bg-strong text-ink-500 hover:text-ink cursor-pointer ml-1"
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
                className="mt-1 flex-shrink-0 w-8 h-8 rounded-full bg-inset border border-line-200 hover:bg-strong flex items-center justify-center text-ink-700 hover:text-ink transition-colors cursor-pointer"
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
                  className="w-full bg-transparent text-ink placeholder:text-ink-300 resize-none outline-none text-base font-sans leading-relaxed scrollbar-hide py-1"
                  autoFocus
                />
              </div>
            </div>

            {/* Prompt Bottom Action Bar */}
            <div className="flex items-center justify-between px-4 py-3 bg-inset border-t border-line-100 relative">
              <div className="flex items-center gap-2">
                {/* Generation Preferences Button ("Ask · Quality") */}
                <div className="relative">
                  <button
                    onClick={() => setShowPrefsPopover(!showPrefsPopover)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
                      showPrefsPopover
                        ? 'bg-strong text-ink border-line-400'
                        : 'bg-inset hover:bg-strong border-line-200 text-ink-700 hover:text-ink'
                    }`}
                  >
                    <SlidersHorizontal className="w-3.5 h-3.5 text-verify" />
                    <span>{generationPreferences.mode === 'ask' ? 'Ask' : 'Auto'} · {generationPreferences.target.toUpperCase()}</span>
                  </button>

                  {/* Preferences Popover Modal */}
                  {showPrefsPopover && (
                    <div
                      className="absolute left-0 bottom-full mb-2 w-72 bg-inset border border-line-300 rounded-xl shadow-lg p-4 z-50 text-xs font-sans space-y-3"
                      onMouseLeave={() => setShowPrefsPopover(false)}
                    >
                      <div className="flex justify-between items-center pb-2 border-b border-line-200">
                        <span className="font-bold text-ink">Generation Preferences</span>
                        <span className="text-[10px] font-mono text-verify">L40S 48GB</span>
                      </div>

                      {/* Ask vs Auto */}
                      <div>
                        <span className="text-[10px] font-mono text-ink-500 block mb-1">When generating media</span>
                        <div className="grid grid-cols-2 gap-1.5 font-mono">
                          <button
                            onClick={() => setGenerationPreferences({ mode: 'ask' })}
                            className={`py-1 rounded border text-center cursor-pointer transition-all ${
                              generationPreferences.mode === 'ask'
                                ? 'bg-verify-soft text-verify border-verify/40 font-bold'
                                : 'bg-ground/40 text-ink-500 border-line-100'
                            }`}
                          >
                            Ask (Confirm)
                          </button>
                          <button
                            onClick={() => setGenerationPreferences({ mode: 'auto' })}
                            className={`py-1 rounded border text-center cursor-pointer transition-all ${
                              generationPreferences.mode === 'auto'
                                ? 'bg-verify-soft text-verify border-verify/40 font-bold'
                                : 'bg-ground/40 text-ink-500 border-line-100'
                            }`}
                          >
                            Auto (Instant)
                          </button>
                        </div>
                      </div>

                      {/* Optimize Target */}
                      <div>
                        <span className="text-[10px] font-mono text-ink-500 block mb-1">Optimize generations</span>
                        <div className="grid grid-cols-4 gap-1 font-mono text-[10px]">
                          {(['quality', 'speed', 'cost', 'custom'] as const).map((tgt) => (
                            <button
                              key={tgt}
                              onClick={() => setGenerationPreferences({ target: tgt })}
                              className={`py-1 rounded border text-center capitalize cursor-pointer transition-all ${
                                generationPreferences.target === tgt
                                  ? 'bg-strong text-ink-900 border-line-400 font-bold'
                                  : 'bg-ground/40 text-ink-500 border-line-100'
                              }`}
                            >
                              {tgt}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Duration */}
                      <div>
                        <span className="text-[10px] font-mono text-ink-500 block mb-1">Duration & Aspect</span>
                        <div className="grid grid-cols-3 gap-1 font-mono text-[10px]">
                          {[4, 8, 16].map((sec) => (
                            <button
                              key={sec}
                              onClick={() => setGenerationPreferences({ duration: sec })}
                              className={`py-1 rounded border text-center cursor-pointer transition-all ${
                                generationPreferences.duration === sec
                                  ? 'bg-strong text-ink border-line-400 font-bold'
                                  : 'bg-ground/40 text-ink-500 border-line-100'
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
                  <div className="text-[11px] text-ink-500 hidden sm:flex items-center gap-1 font-mono">
                    Press <kbd className="px-1.5 py-0.5 rounded bg-inset border border-line-300 text-ink-700 text-[10px]">Tab</kbd> to complete
                  </div>
                )}
              </div>

              {/* Submit / Generate Button */}
              <button
                onClick={handleSubmit}
                disabled={isGenerating}
                className={`flex items-center justify-center h-8 px-3.5 rounded-full transition-all duration-300 gap-1.5 cursor-pointer font-medium text-xs ${
                  isGenerating
                    ? 'bg-verify-soft text-verify border border-verify/30'
                    : prompt.trim().length > 0 || currentSuggestion
                    ? 'bg-accent text-accent-contrast hover:brightness-110 hover:scale-105'
                    : 'bg-inset text-ink-300 cursor-not-allowed'
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

        {/* Generation Status & Error Bar — amber carried "failed" meaning here; the colour is now
            neutral and the word "Error" is added so the message still reads as a failure. */}
        {generationError && (
          <div className="w-full mt-3 p-2.5 rounded-lg bg-inset border border-line-300 text-ink text-xs font-mono flex items-center justify-between">
            <span>Error: {generationError}</span>
            <button onClick={() => setGenerationError(null)} className="text-ink-700 hover:text-ink">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Quick Creative Inspiration Chips */}
        <div className="w-full mt-6">
          <div className="flex items-center gap-2 mb-2 px-1">
            <span className="text-[11px] font-mono text-ink-500 uppercase tracking-wider">
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
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-inset/80 hover:bg-strong border border-line-200 hover:border-line-300 text-xs text-ink-700 hover:text-ink transition-all cursor-pointer group"
                >
                  <Icon className="w-3.5 h-3.5 text-verify group-hover:scale-110 transition-transform" />
                  <span>{chip.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Active Takes Reel Preview Card */}
        <div className="w-full mt-8 bg-raised border border-line-200 rounded-xl p-4">
          <div className="flex items-center justify-between pb-3 border-b border-line-200">
            <div className="flex items-center gap-2 font-mono text-xs">
              <Film className="w-4 h-4 text-verify" />
              <span className="font-bold text-ink">Audition Takes Bin</span>
              <span className="text-ink-500">({takes.length} Takes)</span>
            </div>
            <span className="text-[10px] font-mono text-verify bg-verify-soft px-2 py-0.5 rounded border border-verify/30">
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
                    ? 'bg-inset border-verify'
                    : 'bg-ground/40 border-line-200 hover:border-line-300'
                }`}
              >
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="font-bold text-ink">Take #{take.id}</span>
                  <span className="text-verify text-[10px]">SEED {take.seed}</span>
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono text-ink-500">
                  <span>Pan: +{take.panDeg}°</span>
                  <span>Zoom: {take.zoomRatio}x</span>
                </div>
                <div className="flex items-center justify-center h-12 bg-ground/60 rounded border border-line-100 text-ink-500 group hover:text-ink">
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
