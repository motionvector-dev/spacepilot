import { useState, useEffect } from 'react';
import { CreateWizardHeader } from '../components/create/CreateWizardHeader';
import { PromptScriptStep } from '../components/create/PromptScriptStep';
import { ModelEngineStep } from '../components/create/ModelEngineStep';
import { AudioVoiceStep } from '../components/create/AudioVoiceStep';
import { TakesExplorationGrid, type TakeItem } from '../components/create/TakesExplorationGrid';
import { useGenerateVideo, useJobStatus } from '../hooks/useGenerate';
import type { GenerateRequest } from '../types/api';
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

// GET /api/jobs/{id} returns the worker's raw meta JSON, not the JobResult shape
// declared in types/api.ts (that type only reflects the takes>1 grouped response).
// Read what the backend actually writes (generate.py / engines.py `meta` dicts).
interface JobMeta {
  status?: 'queued' | 'processing' | 'completed' | 'failed';
  error?: string;
  seed?: number;
  width?: number;
  height?: number;
  seconds?: number;
  duration_sec?: number;
  prompt?: string;
}

// /api/generate returns {job_id, meta, patch} for a single take, or
// {jobs: [{job_id, meta, patch}, ...], take_group_id} when takes > 1 — never both.
interface DispatchResponse {
  status: string;
  job_id?: string;
  jobs?: Array<{ job_id: string }>;
}

const MAX_TRACKED_TAKES = 4;
const RENDER_TIMEOUT_MS = 60_000;

export default function CreatePage() {
  // This app has no <Router>; App.tsx routes with pushState. useSearchParams()
  // therefore threw on every load of this page and rendered nothing at all.
  // One read of one parameter does not need a router.
  const extendId = new URLSearchParams(window.location.search).get('extend_id');

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
  const [isImageUploading, setIsImageUploading] = useState(false);
  const [imageUploadError, setImageUploadError] = useState<string | null>(null);

  const [lastImagePath, setLastImagePath] = useState<string | null>(null);
  const [lastImageUrl, setLastImageUrl] = useState<string | null>(null);
  const [lastImageDims, setLastImageDims] = useState<{ width: number; height: number } | null>(null);
  const [detectedAspectEnd, setDetectedAspectEnd] = useState<string | null>(null);
  const [isLastImageUploading, setIsLastImageUploading] = useState(false);
  const [lastImageUploadError, setLastImageUploadError] = useState<string | null>(null);

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
  const [activeJobIds, setActiveJobIds] = useState<string[]>([]);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [dispatchWarning, setDispatchWarning] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);

  const generateMutation = useGenerateVideo();

  // Fixed number of hook calls (Rules of Hooks) covering the largest take batch
  // the UI offers (4). Unused slots pass null, which useJobStatus treats as disabled.
  const jobStatus0 = useJobStatus(activeJobIds[0] ?? null);
  const jobStatus1 = useJobStatus(activeJobIds[1] ?? null);
  const jobStatus2 = useJobStatus(activeJobIds[2] ?? null);
  const jobStatus3 = useJobStatus(activeJobIds[3] ?? null);
  const jobQueries = [jobStatus0, jobStatus1, jobStatus2, jobStatus3].slice(0, activeJobIds.length);

  const hasActiveJobs = activeJobIds.length > 0;
  const isSettled = (status?: string) => status === 'completed' || status === 'failed';
  const allSettled = hasActiveJobs && jobQueries.every((q) => isSettled((q.data as JobMeta | undefined)?.status));
  const failedQueryIndex = jobQueries.findIndex((q) => (q.data as JobMeta | undefined)?.status === 'failed');
  const failedJobMeta = failedQueryIndex >= 0 ? (jobQueries[failedQueryIndex].data as JobMeta) : null;
  const settledCount = jobQueries.filter((q) => isSettled((q.data as JobMeta | undefined)?.status)).length;

  const isGenerating = generateMutation.isPending || (hasActiveJobs && !allSettled && !timedOut);

  // Render timeout mirrors the vanilla studio.js pollJob contract: 60s of no
  // settlement is reported as a timeout, never silently retried as success.
  useEffect(() => {
    if (!hasActiveJobs) return;
    setTimedOut(false);
    const timer = setTimeout(() => setTimedOut(true), RENDER_TIMEOUT_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJobIds.join(',')]);

  const combinedError =
    renderError ||
    (failedJobMeta ? failedJobMeta.error || 'Render failed' : null) ||
    (hasActiveJobs && !allSettled && timedOut ? 'Timed out waiting for the render' : null) ||
    imageUploadError ||
    lastImageUploadError;

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

  // Handle Keyframe 1 Image Selection — local preview only. The real, generate-ready
  // image_path arrives via onImageUploaded once PromptScriptStep's upload completes.
  const handleImageSelected = (file: File) => {
    setIsImageUploading(true);
    setImageUploadError(null);
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

  const handleImageUploaded = (serverPath: string) => {
    setImagePath(serverPath);
    setImageUploadError(null);
    setIsImageUploading(false);
  };

  const handleImageUploadError = (message: string) => {
    // Do not leave a bare filename behind as image_path — the backend can't
    // resolve it, and generation would silently fall through to text-to-video.
    setImagePath(null);
    setImageUploadError(message);
    setIsImageUploading(false);
  };

  const handleImageRemoved = () => {
    setImagePath(null);
    setImageUrl(null);
    setImageDims(null);
    setDetectedAspect(null);
    setIsImageUploading(false);
    setImageUploadError(null);
  };

  // Handle Keyframe 2 (End Keyframe) Image Selection
  const handleLastImageSelected = (file: File) => {
    setIsLastImageUploading(true);
    setLastImageUploadError(null);
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

  const handleLastImageUploaded = (serverPath: string) => {
    setLastImagePath(serverPath);
    setLastImageUploadError(null);
    setIsLastImageUploading(false);
  };

  const handleLastImageUploadError = (message: string) => {
    setLastImagePath(null);
    setLastImageUploadError(message);
    setIsLastImageUploading(false);
  };

  const handleLastImageRemoved = () => {
    setLastImagePath(null);
    setLastImageUrl(null);
    setLastImageDims(null);
    setDetectedAspectEnd(null);
    setIsLastImageUploading(false);
    setLastImageUploadError(null);
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
    setRenderError(null);
    setDispatchWarning(null);
    setActiveJobIds([]);

    const isDual = keyframeMode === 'dual';

    // engine_id is what /api/generate/multi-engine actually reads (engines.py:18);
    // GenerateRequest in types/api.ts still calls this field `engine`, which the
    // backend ignores, so it's cast here rather than sent under the wrong key.
    const payload: GenerateRequest & { engine_id: string } = {
      prompt,
      negative_prompt: negativePrompt || undefined,
      engine_id: selectedEngine,
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
      image_path: imagePath ?? undefined,
      last_image_path: isDual ? (lastImagePath ?? undefined) : undefined,
      bgm_preset: bgmBed !== 'none' ? bgmBed : undefined,
      voice: dialogue.trim() ? voice : undefined,
      target_lufs: ducking ? -16.0 : undefined,
      asset_id: extendId || undefined,
    };

    try {
      const res = (await generateMutation.mutateAsync(payload)) as unknown as DispatchResponse;

      const jobIds = res.jobs && res.jobs.length > 0
        ? res.jobs.map((j) => j.job_id).filter(Boolean).slice(0, MAX_TRACKED_TAKES)
        : res.job_id
        ? [res.job_id]
        : [];

      if (jobIds.length === 0) {
        setRenderError('Generation was dispatched but the server did not return a job id.');
        return;
      }

      setActiveJobIds(jobIds);

      // /api/generate/multi-engine (tried first by useGenerateVideo) has no concept
      // of `takes` and always queues exactly one job — surface the shortfall instead
      // of quietly showing a 1-take result where 4 were requested.
      if (jobIds.length < numTakes) {
        setDispatchWarning(
          `Requested ${numTakes} takes but the server queued ${jobIds.length}. The active engine path does not support batched takes.`
        );
      }
    } catch (err) {
      setRenderError(err instanceof Error ? err.message : 'Failed to dispatch generation job');
    }
  };

  const displayedTakes: TakeItem[] | undefined = hasActiveJobs
    ? jobQueries.reduce<TakeItem[]>((acc, q, idx) => {
        const data = q.data as JobMeta | undefined;
        if (data?.status === 'completed') {
          acc.push({
            id: idx + 1,
            seed: data.seed ?? seed,
            video_url: `/api/media/${activeJobIds[idx]}.mp4`,
            prompt: data.prompt ?? prompt,
            duration_sec: data.duration_sec ?? data.seconds ?? duration,
            fps,
            width: data.width ?? width,
            height: data.height ?? height,
          });
        }
        return acc;
      }, [])
    : undefined;

  const generationProgress = generateMutation.isPending ? 5 : hasActiveJobs ? 50 : 0;
  const generationPhase = generateMutation.isPending
    ? 'Dispatching request to GPU worker...'
    : hasActiveJobs
    ? `Rendering on GPU worker (${settledCount}/${activeJobIds.length} takes ready)...`
    : 'Queued';

  // Format camera descriptor for diff inspector
  const cameraMotions: string[] = [];
  if (cameraPan !== 'static') cameraMotions.push(`Pan ${cameraPan.toUpperCase()}`);
  if (cameraTilt !== 'static') cameraMotions.push(`Tilt ${cameraTilt.toUpperCase()}`);
  if (cameraZoom !== 'static') cameraMotions.push(`Zoom ${cameraZoom.toUpperCase()}`);
  if (cameraRoll !== 'none') cameraMotions.push(cameraRoll === 'orbit' ? 'Orbit 360°' : `Roll ${cameraRoll.toUpperCase()}`);
  const cameraSummary = cameraMotions.length > 0
    ? `${cameraMotions.join(', ')} (Intensity ${cameraIntensity})`
    : 'Static 3D Camera';

  const isDispatchBlocked = Boolean(isGenerating) || isImageUploading || isLastImageUploading;

  return (
    <div className="min-h-screen bg-ground text-ink font-['Plus_Jakarta_Sans'] antialiased">
      <CreateWizardHeader />

      <main className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-8">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[26px] font-bold tracking-tight text-ink flex items-center gap-2.5">
            <span>Generate Video</span>
            {extendId && (
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-inset text-ink-900 border border-line-400">
                Extension Mode
              </span>
            )}
          </h1>
          <p className="text-ink-500 text-[14px]">
            Transform text or reference keyframes into cinematic motion using multi-engine resident DiT orchestration.
          </p>
        </div>

        {combinedError && (
          <div className="bg-danger-soft border border-danger/30 rounded-xl p-4 flex items-center gap-3 text-danger text-sm animate-in fade-in">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <div>
              <span className="font-bold">Generation Error:</span> {combinedError}
            </div>
          </div>
        )}

        {dispatchWarning && (
          <div className="bg-inset border border-line-400 rounded-xl p-4 flex items-center gap-3 text-ink-900 text-sm animate-in fade-in">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <div>
              <span className="font-bold">Partial Dispatch:</span> {dispatchWarning}
            </div>
          </div>
        )}

        {allSettled && !failedJobMeta && (
          <div className="bg-verify-soft border border-verify/30 rounded-xl p-4 flex items-center justify-between text-verify text-sm animate-in fade-in">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 shrink-0" />
              <div>
                <span className="font-bold">Plate Ready · Applied:</span> Video takes generated successfully ({width}×{height} · {fps}fps · {duration.toFixed(1)}s).
              </div>
            </div>
            <a
              href={`/studio?asset_id=${activeJobIds[0]}`}
              className="px-3 py-1.5 rounded-lg bg-verify text-accent-contrast font-bold text-xs hover:opacity-90 transition-colors flex items-center gap-1 cursor-pointer"
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
              onImageUploaded={handleImageUploaded}
              onImageUploadError={handleImageUploadError}
              lastImagePath={lastImagePath}
              lastImageUrl={lastImageUrl}
              lastImageDims={lastImageDims}
              detectedAspectEnd={detectedAspectEnd}
              onLastImageSelected={handleLastImageSelected}
              onLastImageRemoved={handleLastImageRemoved}
              onLastImageUploaded={handleLastImageUploaded}
              onLastImageUploadError={handleLastImageUploadError}
              setSeed={setSeed}
            />

            {/* MotionVector Proposed PatchCard Component */}
            <div className="p-5 bg-surface border border-line-200 rounded-xl shadow-sm hover:border-line-300 transition-colors flex flex-col gap-4">
              <div className="flex justify-between items-center border-b border-line-100 pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-ink-700" />
                  <span className="font-mono text-xs font-bold text-ink-900 uppercase tracking-wider">
                    Proposed Generation Patch
                  </span>
                </div>
                <span className="font-mono text-[11px] text-ink-900 bg-inset px-2.5 py-1 rounded-md border border-line-200">
                  {costBadge}
                </span>
              </div>

              {/* Upfront Fact Block */}
              <div className="p-3.5 bg-inset border border-line-200 rounded-xl flex flex-col gap-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-ink">
                    <div className="w-2 h-2 rounded-full bg-ink-700" />
                    <span>LTX-2.5 Resident DiT Generation</span>
                  </div>
                  <span className="font-mono text-[11px] text-ink-700 bg-inset px-2 py-0.5 rounded border border-line-200">
                    {width}×{height} · {fps}fps · {duration.toFixed(1)}s
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-ink-500">
                  <Info className="w-3.5 h-3.5 text-ink-500 shrink-0" />
                  <span>{computeQuote}</span>
                </div>
              </div>

              {/* Parameter Diff Inspector */}
              <div className="flex flex-col gap-2 pt-1">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] font-mono font-bold text-ink-500 uppercase tracking-wider">
                    Parameter Diff Inspector
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsDiffExpanded(!isDiffExpanded)}
                    className="text-[11px] text-ink-500 hover:text-ink underline cursor-pointer"
                  >
                    {isDiffExpanded ? 'Collapse' : 'Expand'}
                  </button>
                </div>

                {isDiffExpanded && (
                  <div className="flex flex-col gap-1.5 animate-in fade-in duration-200">
                    <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                      <span className="font-mono text-ink-500 uppercase text-[10.5px]">Prompt</span>
                      <div className="flex items-center gap-1.5 max-w-[70%]">
                        <span className="text-ink-300 line-through text-[11px]">empty</span>
                        <span className="text-ink-300">→</span>
                        <span className="text-ink font-medium truncate font-sans text-right">
                          "{prompt.slice(0, 50)}..."
                        </span>
                      </div>
                    </div>

                    {negativePrompt.trim() && (
                      <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                        <span className="font-mono text-ink-500 uppercase text-[10.5px]">Negative Prompt</span>
                        <div className="flex items-center gap-1.5 max-w-[70%]">
                          <span className="text-ink-300 line-through text-[11px]">none</span>
                          <span className="text-ink-300">→</span>
                          <span className="text-ink font-medium truncate font-mono text-[11px] text-right">
                            {negativePrompt.slice(0, 45)}...
                          </span>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                      <span className="font-mono text-ink-500 uppercase text-[10.5px]">Engine Quality</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-ink-300 line-through">Draft (15 steps)</span>
                        <span className="text-ink-300">→</span>
                        <span className="text-ink font-bold">
                          {engineQuality === 'pro' ? 'Pro Cinema (30 steps)' : 'Draft Mode (15 steps)'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                      <span className="font-mono text-ink-500 uppercase text-[10.5px]">Motion Guidance (STG)</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-ink-300 line-through">1.0</span>
                        <span className="text-ink-300">→</span>
                        <span className="text-ink font-bold">{stg.toFixed(1)}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                      <span className="font-mono text-ink-500 uppercase text-[10.5px]">Aspect &amp; Resolution</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-ink-300 line-through">16:9 (1024x576)</span>
                        <span className="text-ink-300">→</span>
                        <span className="text-ink font-bold">{aspect} ({width}×{height})</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                      <span className="font-mono text-ink-500 uppercase text-[10.5px]">Duration &amp; Frames</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-ink-300 line-through">4.0s (97 frames)</span>
                        <span className="text-ink-300">→</span>
                        <span className="text-ink font-bold">{duration.toFixed(1)}s ({totalFrames} frames @ {fps}fps)</span>
                      </div>
                    </div>

                    {cameraMotions.length > 0 && (
                      <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                        <span className="font-mono text-ink-500 uppercase text-[10.5px]">Camera Motion</span>
                        <div className="flex items-center gap-1.5 font-mono text-[11px]">
                          <span className="text-ink-300 line-through">Static</span>
                          <span className="text-ink-300">→</span>
                          <span className="text-ink font-bold">{cameraSummary}</span>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                      <span className="font-mono text-ink-500 uppercase text-[10.5px]">Seed</span>
                      <div className="flex items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-ink-300 line-through">random</span>
                        <span className="text-ink-300">→</span>
                        <span className="text-ink font-bold">
                          {isSeedLocked ? `#${seed} (Locked)` : 'Dynamic (Auto)'}
                        </span>
                      </div>
                    </div>

                    {imagePath && (
                      <div className="flex items-center justify-between p-2 rounded bg-inset border border-line-100 text-xs">
                        <span className="font-mono text-ink-500 uppercase text-[10.5px]">Reference Keyframe(s)</span>
                        <div className="flex items-center gap-1.5 font-mono text-[11px]">
                          <span className="text-ink-300 line-through">none (T2V)</span>
                          <span className="text-ink-300">→</span>
                          <span className="text-ink font-bold truncate max-w-[180px]">
                            {keyframeMode === 'dual' && lastImagePath ? `${imagePath} → ${lastImagePath}` : imagePath}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-between items-center text-[10.5px] font-mono text-ink-500 border-t border-line-100 pt-2">
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
                disabled={isDispatchBlocked}
                className="w-full h-[48px] bg-accent hover:opacity-90 text-accent-contrast text-[14px] font-bold rounded-xl hover:scale-[1.01] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-accent-contrast" />
                    <span>Rendering Video ({generationProgress}%)...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Generate Video (1 Take)</span>
                  </>
                )}
              </button>

              <button
                onClick={() => handleGenerate(4)}
                disabled={isDispatchBlocked}
                className="w-full h-[44px] bg-surface text-ink hover:text-ink text-[13px] font-semibold rounded-xl border border-line-300 hover:bg-raised hover:border-line-500 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 shadow-sm"
              >
                <Grid2X2 className="w-4 h-4 text-ink-700" />
                <span>4-Take Director Grid (Batch 4 Seeds)</span>
              </button>

              <div className="text-center text-[11px] font-mono text-ink-500 mt-0.5">
                Estimated Spot Compute: ~$0.04 - $0.16 (No charge on failure)
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
