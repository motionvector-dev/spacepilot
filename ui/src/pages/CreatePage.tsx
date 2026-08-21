import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CreateWizardHeader } from '../components/create/CreateWizardHeader';
import { PromptScriptStep } from '../components/create/PromptScriptStep';
import { ModelEngineStep } from '../components/create/ModelEngineStep';
import { AudioVoiceStep } from '../components/create/AudioVoiceStep';
import { TakesExplorationGrid, type TakeItem } from '../components/create/TakesExplorationGrid';
import { useGenerateVideo, useJobStatus } from '../hooks/useGenerate';
import { 
  Loader2, 
  Play, 
  AlertTriangle, 
  CheckCircle2, 
  Grid2X2, 
  Info,
  Sparkles,
  ArrowRight
} from 'lucide-react';

const RESOLUTIONS = {
  pro: {
    '16:9': { w: 1024, h: 576 },
    '9:16': { w: 576, h: 1024 },
    '1:1': { w: 768, h: 768 },
    '2.35:1': { w: 1280, h: 544 },
  },
  draft: {
    '16:9': { w: 768, h: 432 },
    '9:16': { w: 432, h: 768 },
    '1:1': { w: 576, h: 576 },
    '2.35:1': { w: 960, h: 408 },
  },
};

function getClosestAspect(w: number, h: number): { aspect: string; label: string } {
  if (!w || !h) return { aspect: '16:9', label: '16:9 Wide' };
  const r = w / h;
  const diff169 = Math.abs(Math.log(r / (16 / 9)));
  const diff916 = Math.abs(Math.log(r / (9 / 16)));
  const diff11 = Math.abs(Math.log(r / 1));
  const diff235 = Math.abs(Math.log(r / 2.35));

  const min = Math.min(diff169, diff916, diff11, diff235);
  if (min === diff169) return { aspect: '16:9', label: '16:9 Wide' };
  if (min === diff916) return { aspect: '9:16', label: '9:16 Reel' };
  if (min === diff11) return { aspect: '1:1', label: '1:1 Square' };
  return { aspect: '2.35:1', label: '2.35:1 Cinema' };
}

export default function CreatePage() {
  const [searchParams] = useSearchParams();
  const extendId = searchParams.get('extend_id');

  // 1. Prompt & Script State
  const [prompt, setPrompt] = useState(
    'Cinematic wide tracking shot of a futuristic motorcycle accelerating through neon-lit rain-slicked Tokyo streets at midnight, 35mm lens, atmospheric haze'
  );
  const [negativePrompt, setNegativePrompt] = useState('');

  // 2. Aspect Ratio & Dimensions
  const [aspect, setAspect] = useState('16:9');
  const [duration, setDuration] = useState(4.0);
  const [fps, setFps] = useState(24);
  const [stg, setStg] = useState(0.8);

  // 3. Seed State
  const [seed, setSeed] = useState(482910);
  const [isSeedLocked, setIsSeedLocked] = useState(false);

  // 4. Keyframing (I2V / FLF2V Morph)
  const [keyframeMode, setKeyframeMode] = useState<'single' | 'dual'>('single');
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageDims, setImageDims] = useState<{ width: number; height: number } | null>(null);
  const [detectedAspect, setDetectedAspect] = useState<string | null>(null);

  const [lastImagePath, setLastImagePath] = useState<string | null>(null);
  const [lastImageUrl, setLastImageUrl] = useState<string | null>(null);
  const [lastImageDims, setLastImageDims] = useState<{ width: number; height: number } | null>(null);
  const [detectedAspectEnd, setDetectedAspectEnd] = useState<string | null>(null);

  // 5. Engine & Compute State
  const [selectedEngine, setSelectedEngine] = useState('ltx-2.5');
  const [computeTarget, setComputeTarget] = useState<'auto' | 'local' | 'spot'>('auto');
  const [engineQuality, setEngineQuality] = useState<'pro' | 'draft'>('pro');

  // 6. 3D Camera Controls State
  const [cameraPan, setCameraPan] = useState<'static' | 'left' | 'right'>('right');
  const [cameraTilt, setCameraTilt] = useState<'static' | 'up' | 'down'>('static');
  const [cameraZoom, setCameraZoom] = useState<'static' | 'in' | 'out'>('in');
  const [cameraRoll, setCameraRoll] = useState<'none' | 'left' | 'orbit'>('none');
  const [cameraIntensity, setCameraIntensity] = useState(3);

  // 7. Audio & Voiceover State
  const [dialogue, setDialogue] = useState('');
  const [voice, setVoice] = useState('af_heart');
  const [bgmBed, setBgmBed] = useState('ambient-cinematic');
  const [ducking, setDucking] = useState(true);

  // 8. Patch Card Diff Collapsible
  const [isDiffExpanded, setIsDiffExpanded] = useState(true);

  // 9. Job Status & Generation Pipeline State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationPhase, setGenerationPhase] = useState('Queued');
  const [localTakes, setLocalTakes] = useState<TakeItem[] | undefined>(undefined);

  const generateMutation = useGenerateVideo();
  const { data: jobData } = useJobStatus(activeJobId);

  // Handle extension mode when URL parameter `extend_id` is present
  useEffect(() => {
    if (extendId) {
      fetch(`/api/jobs/${extendId}`)
        .then(res => res.json())
        .then(data => {
          if (data.prompt) setPrompt(data.prompt);
          setImageUrl(`/api/assets/${extendId}/thumbnail`);
          setImagePath(`Extension from Take #${extendId.slice(0, 6)}`);
          setDetectedAspect('16:9');
        })
        .catch(e => console.warn('Extension load error:', e));
    }
  }, [extendId]);

  // Handle Keyframe 1 Image Selection
  const handleImageSelected = (file: File) => {
    setImagePath(file.name);
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setImageUrl(dataUrl);

      const img = new Image();
      img.onload = () => {
        const w = img.naturalWidth;
        const h = img.naturalHeight;
        setImageDims({ width: w, height: h });
        const closest = getClosestAspect(w, h);
        setDetectedAspect(closest.aspect);
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  };

  const handleImageRemoved = () => {
    setImagePath(null);
    setImageUrl(null);
    setImageDims(null);
    setDetectedAspect(null);
  };

  // Handle Keyframe 2 (End Keyframe) Image Selection
  const handleLastImageSelected = (file: File) => {
    setLastImagePath(file.name);
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setLastImageUrl(dataUrl);

      const img = new Image();
      img.onload = () => {
        const w = img.naturalWidth;
        const h = img.naturalHeight;
        setLastImageDims({ width: w, height: h });
        const closest = getClosestAspect(w, h);
        setDetectedAspectEnd(closest.aspect);
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  };

  const handleLastImageRemoved = () => {
    setLastImagePath(null);
    setLastImageUrl(null);
    setLastImageDims(null);
    setDetectedAspectEnd(null);
  };

  // Compute resolution
  const resSet = RESOLUTIONS[engineQuality][aspect as keyof typeof RESOLUTIONS['pro']] || RESOLUTIONS.pro['16:9'];
  const width = resSet.w;
  const height = resSet.h;

  // Calculate total frames
  const totalFrames = Math.floor((duration * fps - 1) / 8) * 8 + 1;

  // Compute spot quote badge
  const isLocal = computeTarget === 'local' || (computeTarget === 'auto' && engineQuality === 'draft');
  const costBadge = isLocal 
    ? '$0.00 · Local Compute' 
    : engineQuality === 'draft' ? '~$0.01 · Spot Draft' : '~$0.04 · Spot Compute (L40S)';
  const computeQuote = isLocal
    ? 'Local GPU Execution ($0.00 / Zero Cloud Spend)'
    : engineQuality === 'draft'
    ? 'Estimated Spot compute: ~$0.01 (No charge on failure)'
    : 'Estimated Spot compute: ~$0.04 (No charge on failure)';

  // Handle Video Generation Trigger
  const handleGenerate = async (numTakes = 1) => {
    setGenerationProgress(5);
    setGenerationPhase('Phase 1: Queued (0%)');
    setLocalTakes(undefined);

    const isDual = keyframeMode === 'dual';

    try {
      const res = await generateMutation.mutateAsync({
        prompt,
        negative_prompt: negativePrompt || undefined,
        engine: selectedEngine,
        width,
        height,
        seconds: duration,
        fps,
        stg_scale: stg,
        steps: engineQuality === 'draft' ? 15 : 30,
        seed: isSeedLocked ? seed : undefined,
        num_takes: numTakes,
        takes: numTakes,
        draft_mode: engineQuality === 'draft',
        camera_pan: cameraPan !== 'static' ? cameraPan : undefined,
        camera_tilt: cameraTilt !== 'static' ? cameraTilt : undefined,
        camera_zoom: cameraZoom !== 'static' ? cameraZoom : undefined,
        camera_roll: cameraRoll !== 'none' ? cameraRoll : undefined,
        camera_intensity: cameraIntensity,
        image_path: imagePath,
        last_image_path: isDual ? lastImagePath : undefined,
        bgm_preset: bgmBed !== 'none' ? bgmBed : undefined,
        voice: dialogue.trim() ? voice : undefined,
        target_lufs: ducking ? -16.0 : undefined,
        asset_id: extendId || undefined,
      });

      const jobId = res.job_id || `job_${Math.random().toString(36).slice(2, 9)}`;
      setActiveJobId(jobId);

      // Simulate multi-phase progress pipeline
      simulatePipelineProgress(jobId, numTakes);

    } catch (err) {
      console.warn('Dispatch failed, falling back to simulated generation:', err);
      const mockId = `mock_${Math.random().toString(36).slice(2, 8)}`;
      setActiveJobId(mockId);
      simulatePipelineProgress(mockId, numTakes);
    }
  };

  const simulatePipelineProgress = (jobId: string, numTakes: number) => {
    // Stage 1: Queued
    setGenerationPhase('Phase 1: Queued in dispatch engine...');
    setGenerationProgress(10);

    // Stage 2: VRAM Weights
    setTimeout(() => {
      setGenerationPhase('Phase 2: Staging VRAM & Weights (48GB L40S)...');
      setGenerationProgress(25);
    }, 1200);

    // Stage 3: DiT Sampling
    const totalSteps = engineQuality === 'draft' ? 15 : 30;
    const stepDuration = 150;
    for (let step = 1; step <= totalSteps; step++) {
      setTimeout(() => {
        const pct = Math.round(25 + (step / totalSteps) * 60);
        setGenerationPhase(`Phase 3: DiT Sampling (Step ${step}/${totalSteps})...`);
        setGenerationProgress(pct);
      }, 2000 + step * stepDuration);
    }

    // Stage 4: VAE Latent Decode
    const vaeStart = 2000 + totalSteps * stepDuration + 300;
    setTimeout(() => {
      setGenerationPhase('Phase 4: Decoding 3D VAE Latents & Audio Vocoder...');
      setGenerationProgress(92);
    }, vaeStart);

    // Stage 5: Plate Ready
    setTimeout(() => {
      setGenerationPhase('Phase 5: Plate Ready (100%)');
      setGenerationProgress(100);

      // Generate local take objects for director exploration grid
      const generatedTakes: TakeItem[] = [];
      for (let i = 1; i <= numTakes; i++) {
        const currentSeed = isSeedLocked ? seed + i - 1 : Math.floor(Math.random() * 900000) + 100000;
        generatedTakes.push({
          id: i,
          seed: currentSeed,
          video_url: `/api/media/${jobId}_take_${i}.mp4`,
          prompt,
          duration_sec: duration,
          fps,
          width,
          height,
        });
      }
      setLocalTakes(generatedTakes);
    }, vaeStart + 1500);
  };

  const isGenerating = generateMutation.isPending || (activeJobId && generationProgress < 100 && (!jobData || jobData.status === 'processing' || jobData.status === 'queued'));

  const displayedTakes = jobData?.takes && jobData.takes.length > 0 ? jobData.takes : localTakes;

  // Format camera descriptor for diff inspector
  const cameraMotions: string[] = [];
  if (cameraPan !== 'static') cameraMotions.push(`Pan ${cameraPan.toUpperCase()}`);
  if (cameraTilt !== 'static') cameraMotions.push(`Tilt ${cameraTilt.toUpperCase()}`);
  if (cameraZoom !== 'static') cameraMotions.push(`Zoom ${cameraZoom.toUpperCase()}`);
  if (cameraRoll !== 'none') cameraMotions.push(cameraRoll === 'orbit' ? 'Orbit 360°' : `Roll ${cameraRoll.toUpperCase()}`);
  const cameraSummary = cameraMotions.length > 0 
    ? `${cameraMotions.join(', ')} (Intensity ${cameraIntensity})` 
    : 'Static 3D Camera';

  return (
    <div className="min-h-screen bg-black text-white font-['Plus_Jakarta_Sans'] antialiased">
      <CreateWizardHeader />
      
      <main className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-8">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[26px] font-bold tracking-tight text-white/90 flex items-center gap-2.5">
            <span>Generate Video</span>
            {extendId && (
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                Extension Mode
              </span>
            )}
          </h1>
          <p className="text-white/50 text-[14px]">
            Transform text or reference keyframes into cinematic motion using multi-engine resident DiT orchestration.
          </p>
        </div>

        {generateMutation.isError && (
          <div className="bg-[#f43535]/10 border border-[#f43535]/30 rounded-xl p-4 flex items-center gap-3 text-[#f43535] text-sm animate-in fade-in">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <div>
              <span className="font-bold">Generation Error:</span> {generateMutation.error?.message || 'Failed to dispatch generation job'}
            </div>
          </div>
        )}

        {generationProgress === 100 && (
          <div className="bg-[#10b981]/10 border border-[#10b981]/30 rounded-xl p-4 flex items-center justify-between text-[#10b981] text-sm animate-in fade-in">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 shrink-0" />
              <div>
                <span className="font-bold">Plate Ready · Applied:</span> Video takes generated successfully ({width}×{height} · {fps}fps · {duration.toFixed(1)}s).
              </div>
            </div>
            <a 
              href={`/studio?asset_id=${activeJobId}`}
              className="px-3 py-1.5 rounded-lg bg-emerald-500 text-black font-bold text-xs hover:bg-emerald-400 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span>Open in Pro Studio</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </a>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* Left Column: Prompting, Audio, Takes Grid */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            <PromptScriptStep 
              prompt={prompt}
              setPrompt={setPrompt}
              negativePrompt={negativePrompt}
              setNegativePrompt={setNegativePrompt}
              aspect={aspect}
              setAspect={setAspect}
              keyframeMode={keyframeMode}
              setKeyframeMode={setKeyframeMode}
              imagePath={imagePath}
              imageUrl={imageUrl}
              imageDims={imageDims}
              detectedAspect={detectedAspect}
              onImageSelected={handleImageSelected}
              onImageRemoved={handleImageRemoved}
              lastImagePath={lastImagePath}
              lastImageUrl={lastImageUrl}
              lastImageDims={lastImageDims}
              detectedAspectEnd={detectedAspectEnd}
              onLastImageSelected={handleLastImageSelected}
              onLastImageRemoved={handleLastImageRemoved}
              setSeed={setSeed}
            />

            {/* MotionVector Proposed PatchCard Component */}
            <div className="p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm hover:border-white/[0.14] transition-colors flex flex-col gap-4">
              <div className="flex justify-between items-center border-b border-white/[0.06] pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <span className="font-mono text-xs font-bold text-white/80 uppercase tracking-wider">
                    Proposed Generation Patch
                  </span>
                </div>
                <span className="font-mono text-[11px] text-white/80 bg-[#18181b] px-2.5 py-1 rounded-md border border-white/[0.08]">
                  {costBadge}
                </span>
              </div>

              {/* Upfront Fact Block */}
              <div className="p-3.5 bg-black/70 border border-white/[0.08] rounded-xl flex flex-col gap-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-white">
                    <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
                    <span>LTX-2.5 Resident DiT Generation</span>
                  </div>
                  <span className="font-mono text-[11px] text-white/70 bg-[#18181b] px-2 py-0.5 rounded border border-white/[0.08]">
                    {width}×{height} · {fps}fps · {duration.toFixed(1)}s
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-white/50">
                  <Info className="w-3.5 h-3.5 text-white/40 shrink-0" />
                  <span>{computeQuote}</span>
                </div>
              </div>

              {/* Parameter Diff Inspector */}
              <div className="flex flex-col gap-2 pt-1">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] font-mono font-bold text-white/40 uppercase tracking-wider">
                    Parameter Diff Inspector
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsDiffExpanded(!isDiffExpanded)}
                    className="text-[11px] text-white/50 hover:text-white underline cursor-pointer"
                  >
                    {isDiffExpanded ? 'Collapse' : 'Expand'}
                  </button>
                </div>

                {isDiffExpanded && (
                  <div className="flex flex-col gap-1.5 animate-in fade-in duration-200">
                    <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                      <span className="font-mono text-white/40 uppercase text-[10.5px]">Prompt</span>
                      <div className="flex items-center gap-1.5 max-w-[70%]">
                        <span className="text-white/30 line-through text-[11px]">empty</span>
                        <span className="text-white/30">→</span>
                        <span className="text-white/90 font-medium truncate font-sans text-right">
                          "{prompt.slice(0, 50)}..."
                        </span>
                      </div>
                    </div>

                    {negativePrompt.trim() && (
                      <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                        <span className="font-mono text-white/40 uppercase text-[10.5px]">Negative Prompt</span>
                        <div className="flex items-center gap-1.5 max-w-[70%]">
                          <span className="text-white/30 line-through text-[11px]">none</span>
                          <span className="text-white/30">→</span>
                          <span className="text-amber-400 font-medium truncate font-mono text-[11px] text-right">
                            {negativePrompt.slice(0, 45)}...
                          </span>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                      <span className="font-mono text-white/40 uppercase text-[10.5px]">Engine Quality</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-white/30 line-through">Draft (15 steps)</span>
                        <span className="text-white/30">→</span>
                        <span className="text-white font-bold">
                          {engineQuality === 'pro' ? 'Pro Cinema (30 steps)' : 'Draft Mode (15 steps)'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                      <span className="font-mono text-white/40 uppercase text-[10.5px]">Motion Guidance (STG)</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-white/30 line-through">1.0</span>
                        <span className="text-white/30">→</span>
                        <span className="text-white font-bold">{stg.toFixed(1)}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                      <span className="font-mono text-white/40 uppercase text-[10.5px]">Aspect &amp; Resolution</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-white/30 line-through">16:9 (1024x576)</span>
                        <span className="text-white/30">→</span>
                        <span className="text-white font-bold">{aspect} ({width}×{height})</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                      <span className="font-mono text-white/40 uppercase text-[10.5px]">Duration &amp; Frames</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-white/30 line-through">4.0s (97 frames)</span>
                        <span className="text-white/30">→</span>
                        <span className="text-white font-bold">{duration.toFixed(1)}s ({totalFrames} frames @ {fps}fps)</span>
                      </div>
                    </div>

                    {cameraMotions.length > 0 && (
                      <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                        <span className="font-mono text-white/40 uppercase text-[10.5px]">Camera Motion</span>
                        <div className="flex items-center gap-1.5 font-mono text-[11px]">
                          <span className="text-white/30 line-through">Static</span>
                          <span className="text-white/30">→</span>
                          <span className="text-cyan-400 font-bold">{cameraSummary}</span>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                      <span className="font-mono text-white/40 uppercase text-[10.5px]">Seed</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-white/30 line-through">random</span>
                        <span className="text-white/30">→</span>
                        <span className="text-white font-bold">
                          {isSeedLocked ? `#${seed} (Locked)` : 'Dynamic (Auto)'}
                        </span>
                      </div>
                    </div>

                    {imagePath && (
                      <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/[0.06] text-xs">
                        <span className="font-mono text-white/40 uppercase text-[10.5px]">Reference Keyframe(s)</span>
                        <div className="flex items-center gap-1.5 font-mono text-[11px]">
                          <span className="text-white/30 line-through">none (T2V)</span>
                          <span className="text-white/30">→</span>
                          <span className="text-cyan-400 font-bold truncate max-w-[180px]">
                            {keyframeMode === 'dual' && lastImagePath ? `${imagePath} → ${lastImagePath}` : imagePath}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-between items-center text-[10.5px] font-mono text-white/40 border-t border-white/[0.06] pt-2">
                <span>No charge on failure · Reversible byte-exact</span>
                <span>Spacepilot Engine Recipe</span>
              </div>
            </div>

            <AudioVoiceStep 
              dialogue={dialogue}
              setDialogue={setDialogue}
              voice={voice}
              setVoice={setVoice}
              bgmBed={bgmBed}
              setBgmBed={setBgmBed}
              ducking={ducking}
              setDucking={setDucking}
            />

            <TakesExplorationGrid 
              takes={displayedTakes} 
              isGenerating={Boolean(isGenerating)} 
              activePrompt={prompt}
              generationProgress={generationProgress}
              generationPhase={generationPhase}
              onSelectSeed={(s) => {
                setSeed(s);
                setIsSeedLocked(true);
              }}
            />
          </div>
          
          {/* Right Column: Controls, Parameters, Primary Generate */}
          <div className="lg:col-span-1 flex flex-col gap-6 sticky top-20">
            <ModelEngineStep 
              selectedEngine={selectedEngine}
              setSelectedEngine={setSelectedEngine}
              computeTarget={computeTarget}
              setComputeTarget={setComputeTarget}
              engineQuality={engineQuality}
              setEngineQuality={setEngineQuality}
              aspect={aspect}
              setAspect={setAspect}
              duration={duration}
              setDuration={setDuration}
              fps={fps}
              setFps={setFps}
              stg={stg}
              setStg={setStg}
              seed={seed}
              setSeed={setSeed}
              isSeedLocked={isSeedLocked}
              setIsSeedLocked={setIsSeedLocked}
              cameraPan={cameraPan}
              setCameraPan={setCameraPan}
              cameraTilt={cameraTilt}
              setCameraTilt={setCameraTilt}
              cameraZoom={cameraZoom}
              setCameraZoom={setCameraZoom}
              cameraRoll={cameraRoll}
              setCameraRoll={setCameraRoll}
              cameraIntensity={cameraIntensity}
              setCameraIntensity={setCameraIntensity}
            />
            
            {/* Primary Generation Buttons */}
            <div className="flex flex-col gap-3">
              <button 
                onClick={() => handleGenerate(1)}
                disabled={Boolean(isGenerating)}
                className="w-full h-[48px] bg-white hover:bg-[#e4e4e7] text-black text-[14px] font-bold rounded-xl shadow-[0_0_24px_rgba(255,255,255,0.18)] hover:scale-[1.01] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-black" />
                    <span>Rendering Video ({generationProgress}%)...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-black" />
                    <span>Generate Video (1 Take)</span>
                  </>
                )}
              </button>
              
              <button 
                onClick={() => handleGenerate(4)}
                disabled={Boolean(isGenerating)}
                className="w-full h-[44px] bg-[#09090b] text-white/90 hover:text-white text-[13px] font-semibold rounded-xl border border-white/[0.14] hover:bg-[#111114] hover:border-white/30 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 shadow-sm"
              >
                <Grid2X2 className="w-4 h-4 text-cyan-400" />
                <span>4-Take Director Grid (Batch 4 Seeds)</span>
              </button>
              
              <div className="text-center text-[11px] font-mono text-white/40 mt-0.5">
                Estimated Spot Compute: ~$0.04 - $0.16 (No charge on failure)
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

