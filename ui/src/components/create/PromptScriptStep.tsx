import { useState, useRef } from 'react';
import { useEnhancePrompt, useDecomposeStoryboard, useUploadImage } from '../../hooks/useGenerate';
import type { StoryboardScene } from '../../types/api';
import {
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronRight,
  Image as ImageIcon,
  X,
  Zap,
  Film,
  AlertTriangle,
  Check,
  Layers
} from 'lucide-react';

interface PromptScriptStepProps {
  prompt: string;
  setPrompt: (p: string) => void;
  negativePrompt: string;
  setNegativePrompt: (np: string) => void;
  aspect: string;
  setAspect: (a: string) => void;
  keyframeMode: 'single' | 'dual';
  setKeyframeMode: (mode: 'single' | 'dual') => void;
  imagePath: string | null;
  imageUrl: string | null;
  imageDims: { width: number; height: number } | null;
  detectedAspect: string | null;
  onImageSelected: (file: File) => void;
  onImageRemoved: () => void;
  // Called once the server has accepted the upload, with the resolved server-side
  // path (assets.py's `image_path`) that /api/generate actually needs as image_path.
  onImageUploaded?: (imagePath: string) => void;
  onImageUploadError?: (message: string) => void;
  lastImagePath: string | null;
  lastImageUrl: string | null;
  lastImageDims: { width: number; height: number } | null;
  detectedAspectEnd: string | null;
  onLastImageSelected: (file: File) => void;
  onLastImageRemoved: () => void;
  onLastImageUploaded?: (imagePath: string) => void;
  onLastImageUploadError?: (message: string) => void;
  setSeed?: (s: number) => void;
}

const STYLE_PRESETS = [
  { label: 'Cinematic 35mm', tokens: 'Cinematic 35mm, anamorphic lens flare, shallow depth of field, 8k photo' },
  { label: 'Sci-Fi Noir', tokens: 'Dark sci-fi noir, high contrast, atmospheric fog, moody neon backlighting' },
  { label: 'Hyperreal Nature', tokens: 'Hyperrealistic nature documentary, golden hour sun, macro detail, photoreal' },
  { label: 'Retro Anime', tokens: '80s retro anime aesthetic, hand-drawn keyframes, vivid color palette' },
  { label: 'Macro Dynamics', tokens: 'Macro extreme close-up, liquid dynamics, volumetric refraction, ultra-crisp' },
];

const NEGATIVE_PRESETS = [
  'blurry',
  'low quality',
  'distorted',
  'watermark',
  'cartoon',
  'bad anatomy',
  'overexposed',
  'grainy artifacts',
];

export function PromptScriptStep({
  prompt,
  setPrompt,
  negativePrompt,
  setNegativePrompt,
  aspect,
  setAspect,
  keyframeMode,
  setKeyframeMode,
  imagePath,
  imageUrl,
  imageDims,
  detectedAspect,
  onImageSelected,
  onImageRemoved,
  onImageUploaded,
  onImageUploadError,
  lastImagePath,
  lastImageUrl,
  lastImageDims,
  detectedAspectEnd,
  onLastImageSelected,
  onLastImageRemoved,
  onLastImageUploaded,
  onLastImageUploadError,
  setSeed,
}: PromptScriptStepProps) {
  const [isNegativeOpen, setIsNegativeOpen] = useState(false);
  const [isStoryboardOpen, setIsStoryboardOpen] = useState(false);

  // Storyboard Decomposer State
  const [storyboardScript, setStoryboardScript] = useState('');
  const [storyboardDuration, setStoryboardDuration] = useState('60.0');
  const [storyboardScenes, setStoryboardScenes] = useState(6);
  const [storyboardStyle, setStoryboardStyle] = useState('Cinematic 35mm Hollywood');
  const [decomposedScenes, setDecomposedScenes] = useState<StoryboardScene[]>([]);
  const [lockedSeed, setLockedSeed] = useState<number | null>(null);

  const startFileInputRef = useRef<HTMLInputElement>(null);
  const endFileInputRef = useRef<HTMLInputElement>(null);

  const enhanceMutation = useEnhancePrompt();
  const decomposeMutation = useDecomposeStoryboard();
  const uploadImageMutation = useUploadImage();

  const handleEnhance = async () => {
    if (!prompt.trim()) {
      setPrompt('Cinematic wide tracking shot of a sleek cybernetic hovercraft gliding through misty mountain ravines at twilight, volumetric clouds, 35mm anamorphic lens');
      return;
    }
    try {
      const res = await enhanceMutation.mutateAsync(prompt);
      if (res.enhanced_prompt) {
        setPrompt(res.enhanced_prompt);
      }
    } catch {
      setPrompt(`${prompt}, cinematic lighting, photorealistic, 8k resolution, highly detailed, atmospheric haze, 35mm photograph`);
    }
  };

  const handleApplyStyle = (tokens: string) => {
    const trimmed = prompt.trim();
    if (trimmed) {
      setPrompt(`${trimmed}, ${tokens}`);
    } else {
      setPrompt(tokens);
    }
  };

  const handleApplyNegativeToken = (token: string) => {
    const trimmed = negativePrompt.trim();
    if (!trimmed) {
      setNegativePrompt(token);
    } else if (!trimmed.toLowerCase().includes(token.toLowerCase())) {
      setNegativePrompt(`${trimmed}, ${token}`);
    }
  };

  // useUploadImage falls back to { image_path: file.name } instead of throwing when
  // /api/upload-image responds non-2xx, so a bare-filename echo is the only signal
  // that the "success" is actually a swallowed failure — /api/generate can never
  // resolve a bare filename as a real path (generation.py's Path(...).exists() check).
  const isUnresolvedUploadFallback = (resolvedPath: string, file: File) => resolvedPath === file.name;

  const uploadStartImage = (file: File) => {
    onImageSelected(file);
    uploadImageMutation.mutate(file, {
      onSuccess: (data) => {
        if (isUnresolvedUploadFallback(data.image_path, file)) {
          onImageUploadError?.('Image upload failed — the server did not store the file.');
          return;
        }
        onImageUploaded?.(data.image_path);
      },
      onError: (err) => onImageUploadError?.(err.message),
    });
  };

  const uploadEndImage = (file: File) => {
    onLastImageSelected(file);
    uploadImageMutation.mutate(file, {
      onSuccess: (data) => {
        if (isUnresolvedUploadFallback(data.image_path, file)) {
          onLastImageUploadError?.('Image upload failed — the server did not store the file.');
          return;
        }
        onLastImageUploaded?.(data.image_path);
      },
      onError: (err) => onLastImageUploadError?.(err.message),
    });
  };

  const handleStartFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadStartImage(file);
  };

  const handleEndFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadEndImage(file);
  };

  const handleDropStart = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) uploadStartImage(file);
  };

  const handleDropEnd = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) uploadEndImage(file);
  };

  const handleRunStoryboard = async () => {
    const script = storyboardScript.trim() || prompt.trim();
    if (!script) return;

    try {
      const res = await decomposeMutation.mutateAsync({
        script,
        target_duration_sec: parseFloat(storyboardDuration),
        scene_count: storyboardScenes,
        style: storyboardStyle,
      });

      if (res.scenes) {
        setDecomposedScenes(res.scenes);
        setLockedSeed(res.character_seed);
      }
    } catch {
      // Fallback handled in mutation
    }
  };

  const handleUseScene = (scene: StoryboardScene) => {
    setPrompt(scene.prompt);
    if (setSeed && scene.character_seed) {
      setSeed(scene.character_seed);
    }
    setIsStoryboardOpen(false);
  };

  // Check aspect mismatch for Dual Keyframe FLF2V
  const isAspectMismatch = keyframeMode === 'dual' &&
    Boolean(detectedAspect && detectedAspectEnd && detectedAspect !== detectedAspectEnd);

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Prompt Definition Card */}
      <div className="flex flex-col gap-4 p-5 bg-surface border border-line-200 rounded-xl hover:border-line-300 transition-colors">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <h2 className="text-[13px] font-semibold text-ink-700 uppercase tracking-wider">Prompt Definition</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (prompt.trim() && !storyboardScript.trim()) {
                  setStoryboardScript(prompt.trim());
                }
                setIsStoryboardOpen(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-inset border border-line-300 text-xs font-semibold text-ink-900 hover:text-ink hover:border-line-500 hover:bg-strong transition-all cursor-pointer"
              title="Gemini Storyboard & Screenplay Decomposer (60s -> 6-8 Scenes)"
            >
              <Film className="w-3 h-3 text-ink-700" />
              <span>Decompose Script</span>
            </button>
            <button
              onClick={handleEnhance}
              disabled={enhanceMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-inset border border-line-300 text-xs font-semibold text-ink-900 hover:text-ink hover:border-line-500 hover:bg-strong transition-all cursor-pointer disabled:opacity-50"
              title="AI Prompt Expansion"
            >
              {enhanceMutation.isPending ? (
                <Loader2 className="w-3 h-3 animate-spin text-agent" />
              ) : (
                <Sparkles className="w-3 h-3 text-agent" />
              )}
              <span>{enhanceMutation.isPending ? 'Enhancing...' : 'Enhance'}</span>
            </button>
          </div>
        </div>

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="w-full h-32 p-3.5 bg-ground border border-line-300 rounded-lg text-[14.5px] text-ink focus:outline-none focus:border-line-500 focus:ring-1 focus:ring-line-500 transition-all resize-y placeholder-ink-300 leading-relaxed font-sans"
          placeholder="Describe the scene with rich visual details... (e.g. Cinematic wide tracking shot of a futuristic motorcycle accelerating through neon-lit rain-slicked Tokyo streets at midnight, 35mm lens, atmospheric haze)"
        />

        <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1 scrollbar-none">
          <div className="flex items-center gap-2">
            {STYLE_PRESETS.map((preset) => (
              <button
                key={preset.label}
                onClick={() => handleApplyStyle(preset.tokens)}
                className="px-2.5 py-1 rounded-full bg-inset hover:bg-strong border border-line-200 hover:border-line-400 text-[11px] font-medium text-ink-700 hover:text-ink transition-all whitespace-nowrap cursor-pointer"
              >
                {preset.label}
              </button>
            ))}
          </div>
          <span className="text-[11px] font-mono text-ink-500 whitespace-nowrap shrink-0">
            {prompt.length} / 4000
          </span>
        </div>

        {/* 2. Negative Prompt Collapsible Field */}
        <div className="border-t border-line-100 pt-3 flex flex-col gap-2.5">
          <button
            type="button"
            onClick={() => setIsNegativeOpen(!isNegativeOpen)}
            className="flex items-center justify-between text-left group cursor-pointer"
          >
            <div className="flex items-center gap-1.5 text-xs font-semibold text-ink-700 group-hover:text-ink transition-colors">
              {isNegativeOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              <span>Negative Prompt (Optional Filter)</span>
              {negativePrompt.trim() && (
                <span className="ml-1.5 px-1.5 py-0.2 rounded bg-inset text-ink border border-line-400 font-mono text-[10px]">
                  Active
                </span>
              )}
            </div>
            <span className="text-[11px] font-mono text-ink-500">
              {negativePrompt.length > 0 ? `${negativePrompt.length} chars` : 'Collapsed'}
            </span>
          </button>

          {isNegativeOpen && (
            <div className="flex flex-col gap-2 mt-1 animate-in fade-in duration-200">
              <textarea
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                rows={2}
                className="w-full p-2.5 bg-ground border border-line-300 rounded-lg text-xs text-ink focus:outline-none focus:border-line-500 placeholder-ink-300 font-mono"
                placeholder="Specify unwanted elements... (e.g. blurry, low quality, distorted anatomy, cartoon, watermark, glitch)"
              />
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] font-semibold text-ink-500 uppercase mr-1">Quick Filters:</span>
                {NEGATIVE_PRESETS.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => handleApplyNegativeToken(tag)}
                    className="px-2 py-0.5 rounded bg-inset hover:bg-strong border border-line-100 text-[10.5px] text-ink-700 hover:text-ink font-mono transition-colors cursor-pointer"
                  >
                    +{tag}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Keyframing Mode & Dual Image Dropzones */}
      <div className="flex flex-col gap-4 p-5 bg-surface border border-line-200 rounded-xl hover:border-line-300 transition-colors">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-ink-700" />
            <h2 className="text-[13px] font-semibold text-ink-700 uppercase tracking-wider">Keyframe Grounding</h2>
          </div>
          {/* Keyframe Mode Segmented Control */}
          <div className="flex bg-ground p-0.5 rounded-lg border border-line-200">
            <button
              onClick={() => setKeyframeMode('single')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                keyframeMode === 'single'
                  ? 'bg-inset text-ink border border-line-300'
                  : 'text-ink-500 hover:text-ink-900'
              }`}
            >
              Single Keyframe (I2V)
            </button>
            <button
              onClick={() => setKeyframeMode('dual')}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                keyframeMode === 'dual'
                  ? 'bg-inset text-ink border border-line-300'
                  : 'text-ink-500 hover:text-ink-900'
              }`}
            >
              Dual Keyframe (FLF2V Morph)
            </button>
          </div>
        </div>

        {/* Aspect Mismatch Alert */}
        {isAspectMismatch && (
          <div className="flex items-start gap-2.5 p-3 rounded-lg bg-inset border border-line-400 text-ink text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-ink-700" />
            <div>
              <span className="font-bold">Aspect Ratio Mismatch:</span> Start keyframe is{' '}
              <span className="font-mono">{detectedAspect}</span> while end keyframe is{' '}
              <span className="font-mono">{detectedAspectEnd}</span>. FLF2V morph requires matching frame resolutions.
            </div>
          </div>
        )}

        <div className={`grid ${keyframeMode === 'dual' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'} gap-4`}>
          {/* First Keyframe Dropzone */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center">
              <span className="text-[11px] font-bold text-ink-500 uppercase tracking-wider">
                {keyframeMode === 'dual' ? 'Start Keyframe (Frame 0)' : 'Reference Keyframe (I2V)'}
              </span>
              {imageDims && (
                <span className="text-[10.5px] font-mono text-ink-500">
                  {imageDims.width}×{imageDims.height}
                </span>
              )}
            </div>

            <input
              type="file"
              ref={startFileInputRef}
              accept="image/*"
              className="hidden"
              onChange={handleStartFileChange}
            />

            {!imageUrl ? (
              <div
                onClick={() => startFileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDropStart}
                className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-line-300 hover:border-line-500 bg-ground/40 hover:bg-ground/80 rounded-xl cursor-pointer transition-all gap-2 group min-h-[140px]"
              >
                <div className="w-10 h-10 rounded-full bg-raised border border-line-200 flex items-center justify-center text-ink-500 group-hover:text-ink-900 group-hover:border-line-400 transition-all">
                  <ImageIcon className="w-5 h-5" />
                </div>
                <div className="text-center">
                  <p className="text-xs font-semibold text-ink-900 group-hover:text-ink">
                    Drop start reference image or browse
                  </p>
                  <p className="text-[11px] text-ink-500">PNG, JPG, WebP up to 20MB</p>
                </div>
              </div>
            ) : (
              <div className="relative p-3 bg-ground border border-line-300 rounded-xl flex flex-col gap-2.5 group">
                <div className="relative max-h-48 rounded-lg overflow-hidden bg-raised flex items-center justify-center border border-line-200">
                  <img
                    src={imageUrl}
                    alt="Start Keyframe"
                    className="max-h-48 w-full object-contain rounded-lg"
                  />
                  <button
                    type="button"
                    onClick={onImageRemoved}
                    className="absolute top-2 right-2 p-1.5 rounded-full bg-ground/80 hover:bg-danger text-ink-700 hover:text-white transition-all cursor-pointer backdrop-blur-md"
                    title="Remove reference keyframe"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center gap-1.5 font-mono text-[11px] text-ink-700 bg-raised px-2 py-0.5 rounded border border-line-200">
                    <span>{imageDims ? `${imageDims.width}×${imageDims.height}` : imagePath}</span>
                    {detectedAspect && (
                      <>
                        <span className="text-ink-300">·</span>
                        <span className="text-ink-700">{detectedAspect}</span>
                      </>
                    )}
                  </div>

                  {detectedAspect && (
                    <button
                      type="button"
                      onClick={() => setAspect(detectedAspect)}
                      className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-semibold transition-all cursor-pointer ${
                        aspect === detectedAspect
                          ? 'bg-verify-soft text-verify border border-verify/30'
                          : 'bg-inset text-ink-900 hover:text-ink border border-line-300'
                      }`}
                    >
                      {aspect === detectedAspect ? (
                        <>
                          <Check className="w-3 h-3 text-verify" />
                          <span>Matched</span>
                        </>
                      ) : (
                        <>
                          <Zap className="w-3 h-3 text-ink-700" />
                          <span>Auto-Aspect</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* End Keyframe Dropzone (FLF2V Dual Mode) */}
          {keyframeMode === 'dual' && (
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-bold text-ink-500 uppercase tracking-wider">
                  End Keyframe (Frame End - Morph)
                </span>
                {lastImageDims && (
                  <span className="text-[10.5px] font-mono text-ink-500">
                    {lastImageDims.width}×{lastImageDims.height}
                  </span>
                )}
              </div>

              <input
                type="file"
                ref={endFileInputRef}
                accept="image/*"
                className="hidden"
                onChange={handleEndFileChange}
              />

              {!lastImageUrl ? (
                <div
                  onClick={() => endFileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDropEnd}
                  className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-line-300 hover:border-line-500 bg-ground/40 hover:bg-ground/80 rounded-xl cursor-pointer transition-all gap-2 group min-h-[140px]"
                >
                  <div className="w-10 h-10 rounded-full bg-raised border border-line-200 flex items-center justify-center text-ink-500 group-hover:text-ink-900 group-hover:border-line-400 transition-all">
                    <ImageIcon className="w-5 h-5" />
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-semibold text-ink-900 group-hover:text-ink">
                      Drop morph destination keyframe
                    </p>
                    <p className="text-[11px] text-ink-500">FLF2V end frame target</p>
                  </div>
                </div>
              ) : (
                <div className="relative p-3 bg-ground border border-line-300 rounded-xl flex flex-col gap-2.5 group">
                  <div className="relative max-h-48 rounded-lg overflow-hidden bg-raised flex items-center justify-center border border-line-200">
                    <img
                      src={lastImageUrl}
                      alt="End Keyframe"
                      className="max-h-48 w-full object-contain rounded-lg"
                    />
                    <button
                      type="button"
                      onClick={onLastImageRemoved}
                      className="absolute top-2 right-2 p-1.5 rounded-full bg-ground/80 hover:bg-danger text-ink-700 hover:text-white transition-all cursor-pointer backdrop-blur-md"
                      title="Remove end keyframe"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-ink-700 bg-raised px-2 py-0.5 rounded border border-line-200">
                      <span>{lastImageDims ? `${lastImageDims.width}×${lastImageDims.height}` : lastImagePath}</span>
                      {detectedAspectEnd && (
                        <>
                          <span className="text-ink-300">·</span>
                          <span className="text-ink-700">{detectedAspectEnd}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 4. Gemini Storyboard & Screenplay Decomposer Modal */}
      {isStoryboardOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-2xl bg-raised border border-line-300 rounded-2xl p-6 flex flex-col gap-5 shadow-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-line-200 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-inset border border-line-300 flex items-center justify-center text-ink-700">
                  <Film className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-ink">Gemini Storyboard &amp; Script Decomposer</h3>
                  <p className="text-xs text-ink-500">
                    Deconstruct full narratives into 4–8 cinematic shots with locked character seeds.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsStoryboardOpen(false)}
                className="p-2 rounded-lg bg-inset hover:bg-strong text-ink-700 hover:text-ink transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <label className="text-[11px] font-bold text-ink-500 uppercase tracking-wider font-mono">
                Full Narrative / Screenplay Script
              </label>
              <textarea
                value={storyboardScript}
                onChange={(e) => setStoryboardScript(e.target.value)}
                rows={4}
                className="w-full p-3.5 bg-ground border border-line-300 rounded-lg text-sm text-ink focus:outline-none focus:border-line-500 leading-relaxed font-sans placeholder-ink-300"
                placeholder="Paste a 60-second narrative story or script here... (e.g. A solitary cybernetic samurai wanders through rain-drenched Neo-Tokyo, discovers an ancient glowing temple hidden beneath skyscrapers, and steps through a portal of pure starlight into hyperspace.)"
              />

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] font-semibold text-ink-700">Target Duration</label>
                  <select
                    value={storyboardDuration}
                    onChange={(e) => setStoryboardDuration(e.target.value)}
                    className="bg-ground border border-line-300 rounded-md px-3 py-2 text-xs text-ink focus:outline-none cursor-pointer"
                  >
                    <option value="30.0">30s (Short Promo)</option>
                    <option value="45.0">45s (Fast Narrative)</option>
                    <option value="60.0">60s (Standard Storyboard)</option>
                    <option value="90.0">90s (Extended Short)</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] font-semibold text-ink-700">Scene Count</label>
                  <select
                    value={storyboardScenes}
                    onChange={(e) => setStoryboardScenes(parseInt(e.target.value, 10))}
                    className="bg-ground border border-line-300 rounded-md px-3 py-2 text-xs text-ink focus:outline-none cursor-pointer"
                  >
                    <option value={4}>4 Scenes (Compact)</option>
                    <option value={6}>6 Scenes (Recommended)</option>
                    <option value={8}>8 Scenes (Deep Directing)</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] font-semibold text-ink-700">Directing Style</label>
                  <select
                    value={storyboardStyle}
                    onChange={(e) => setStoryboardStyle(e.target.value)}
                    className="bg-ground border border-line-300 rounded-md px-3 py-2 text-xs text-ink focus:outline-none cursor-pointer"
                  >
                    <option value="Cinematic 35mm Hollywood">Cinematic 35mm Hollywood</option>
                    <option value="Sci-Fi Cyberpunk Noir">Sci-Fi Cyberpunk Noir</option>
                    <option value="Bioluminescent Nature Documentary">Nature Documentary</option>
                    <option value="Anime Masterpiece Studio Ghibli">Anime Masterpiece</option>
                  </select>
                </div>
              </div>

              <button
                onClick={handleRunStoryboard}
                disabled={decomposeMutation.isPending || (!storyboardScript.trim() && !prompt.trim())}
                className="w-full py-2.5 mt-2 bg-accent hover:brightness-110 text-accent-contrast font-bold text-xs uppercase tracking-wider rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {decomposeMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Deconstructing Narrative...</span>
                  </>
                ) : (
                  <>
                    <Film className="w-4 h-4" />
                    <span>Deconstruct Narrative</span>
                  </>
                )}
              </button>
            </div>

            {/* Decomposed Output Grid */}
            {decomposedScenes.length > 0 && (
              <div className="border-t border-line-200 pt-4 flex flex-col gap-3">
                <div className="flex justify-between items-center font-mono text-xs">
                  <span className="font-bold text-ink">
                    Generated Storyboard ({decomposedScenes.length} Scenes · {storyboardDuration}s Total)
                  </span>
                  {lockedSeed && (
                    <span className="text-verify">
                      Locked Character Seed: #{lockedSeed}
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-72 overflow-y-auto pr-1">
                  {decomposedScenes.map((sc, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 bg-ground/60 border border-line-200 hover:border-line-400 rounded-xl flex flex-col gap-2 transition-colors"
                    >
                      <div className="flex items-center justify-between text-[11px] font-mono">
                        <span className="font-bold text-ink-900">Scene {sc.scene_idx || idx + 1} · {sc.duration_sec}s</span>
                        <span className="px-1.5 py-0.5 rounded bg-agent-soft text-agent border border-agent-border">
                          {sc.camera_motion || 'Dolly In'}
                        </span>
                      </div>
                      <div className="font-bold text-xs text-ink">{sc.title || `Shot ${idx + 1}`}</div>
                      <p className="text-[11.5px] text-ink-700 line-clamp-3 leading-relaxed">
                        {sc.prompt}
                      </p>
                      <div className="pt-1 text-[10px] font-mono text-ink-500 border-t border-line-100 flex justify-between">
                        <span>{sc.shot_type || 'Tracking'}</span>
                        <span>{sc.lighting || 'Cinematic'}</span>
                      </div>
                      <button
                        onClick={() => handleUseScene(sc)}
                        className="w-full mt-1 py-1.5 rounded bg-inset hover:bg-strong border border-line-300 text-xs font-semibold text-ink transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                      >
                        <Zap className="w-3 h-3" />
                        <span>Use Scene in Prompt</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
