import { useState } from 'react';
import { CreateWizardHeader } from '../components/create/CreateWizardHeader';
import { PromptScriptStep } from '../components/create/PromptScriptStep';
import { ModelEngineStep } from '../components/create/ModelEngineStep';
import { AudioVoiceStep } from '../components/create/AudioVoiceStep';
import { TakesExplorationGrid } from '../components/create/TakesExplorationGrid';
import { useGenerateVideo, useJobStatus } from '../hooks/useGenerate';
import { Loader2, Play, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function CreatePage() {
  const [prompt, setPrompt] = useState('Cinematic wide tracking shot of a futuristic motorcycle accelerating through neon-lit rain-slicked Tokyo streets at midnight, 35mm lens, atmospheric haze');
  const [aspect, setAspect] = useState('16:9');
  const [cameraTags, setCameraTags] = useState<string[]>(['Pan Right', 'Dolly In']);
  const [selectedEngine, setSelectedEngine] = useState('ltx-2.5');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const generateMutation = useGenerateVideo();
  const { data: jobData } = useJobStatus(activeJobId);

  const handleGenerate = async (numTakes = 1) => {
    let width = 1280;
    let height = 720;
    if (aspect === '9:16') {
      width = 720;
      height = 1280;
    } else if (aspect === '1:1') {
      width = 720;
      height = 720;
    } else if (aspect === '2.35:1') {
      width = 1280;
      height = 544;
    }

    try {
      const res = await generateMutation.mutateAsync({
        prompt,
        engine: selectedEngine,
        width,
        height,
        num_takes: numTakes,
        camera_pan: cameraTags.includes('Pan Right') ? 'right' : undefined,
        camera_zoom: cameraTags.includes('Dolly In') ? 'in' : undefined,
        seconds: 4.0,
      });

      if (res.job_id) {
        setActiveJobId(res.job_id);
      }
    } catch {
      // Handled by generateMutation.isError
    }
  };

  const isGenerating = generateMutation.isPending || (activeJobId && jobData?.status !== 'completed' && jobData?.status !== 'failed');

  return (
    <div className="min-h-screen bg-black text-white font-['Plus_Jakarta_Sans']">
      <CreateWizardHeader />
      
      <main className="max-w-5xl mx-auto px-6 py-10 flex flex-col gap-8">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[26px] font-bold tracking-tight text-white/90">Generate Video</h1>
          <p className="text-white/50 text-[14px]">Transform text or reference keyframes into cinematic motion using multi-engine orchestration.</p>
        </div>

        {generateMutation.isError && (
          <div className="bg-[#f43535]/10 border border-[#f43535]/30 rounded-xl p-4 flex items-center gap-3 text-[#f43535] text-sm">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <div>
              <span className="font-bold">Generation Error:</span> {generateMutation.error?.message || 'Failed to dispatch generation job'}
            </div>
          </div>
        )}

        {jobData?.status === 'completed' && (
          <div className="bg-[#10b981]/10 border border-[#10b981]/30 rounded-xl p-4 flex items-center gap-3 text-[#10b981] text-sm">
            <CheckCircle2 className="w-5 h-5 shrink-0" />
            <div>
              <span className="font-bold">Generation Completed:</span> Video takes are ready in the exploration grid below.
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-2 flex flex-col gap-6">
            <PromptScriptStep 
              prompt={prompt}
              setPrompt={setPrompt}
              aspect={aspect}
              setAspect={setAspect}
              cameraTags={cameraTags}
              setCameraTags={setCameraTags}
            />
            <AudioVoiceStep />
            <TakesExplorationGrid 
              takes={jobData?.takes} 
              isGenerating={Boolean(isGenerating)} 
            />
          </div>
          
          <div className="lg:col-span-1 flex flex-col gap-6 sticky top-20">
            <ModelEngineStep 
              selected={selectedEngine}
              setSelected={setSelectedEngine}
            />
            
            <div className="flex flex-col gap-3">
              <button 
                onClick={() => handleGenerate(1)}
                disabled={Boolean(isGenerating)}
                className="w-full h-[46px] bg-white text-black text-[14px] font-bold rounded-lg shadow-[0_0_20px_rgba(255,255,255,0.15)] hover:bg-[#e4e4e7] hover:scale-[1.01] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Rendering... {jobData?.progress ? `${jobData.progress}%` : ''}</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-black" />
                    <span>Generate Video</span>
                  </>
                )}
              </button>
              
              <button 
                onClick={() => handleGenerate(4)}
                disabled={Boolean(isGenerating)}
                className="w-full h-[42px] bg-[#09090b] text-white/80 text-[13px] font-semibold rounded-lg border border-white/[0.14] hover:bg-[#111114] hover:text-white transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                <span>4-Take Director Grid (Batch)</span>
              </button>
              
              <div className="text-center text-[11px] font-mono text-white/40 mt-1">
                Estimated Spot Compute: ~$0.16 (No charge on failure)
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
