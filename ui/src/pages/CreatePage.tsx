
import { CreateWizardHeader } from '../components/create/CreateWizardHeader';
import { PromptScriptStep } from '../components/create/PromptScriptStep';
import { ModelEngineStep } from '../components/create/ModelEngineStep';
import { AudioVoiceStep } from '../components/create/AudioVoiceStep';
import { TakesExplorationGrid } from '../components/create/TakesExplorationGrid';

export default function CreatePage() {
  return (
    <div className="min-h-screen bg-black text-white font-['Plus_Jakarta_Sans']">
      <CreateWizardHeader />
      
      <main className="max-w-5xl mx-auto px-6 py-10 flex flex-col gap-8">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-[26px] font-bold tracking-tight text-white/90">Generate Video</h1>
          <p className="text-white/50 text-[14px]">Transform text or reference keyframes into cinematic motion using multi-engine orchestration.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-2 flex flex-col gap-6">
            <PromptScriptStep />
            <AudioVoiceStep />
            <TakesExplorationGrid />
          </div>
          
          <div className="lg:col-span-1 flex flex-col gap-6 sticky top-20">
            <ModelEngineStep />
            
            <div className="flex flex-col gap-3">
              <button className="w-full h-[46px] bg-white text-black text-[14px] font-bold rounded-lg shadow-[0_0_20px_rgba(255,255,255,0.15)] hover:bg-[#e4e4e7] hover:scale-[1.01] transition-all flex items-center justify-center gap-2">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Generate Video
              </button>
              
              <button className="w-full h-[42px] bg-[#09090b] text-white/80 text-[13px] font-semibold rounded-lg border border-white/[0.14] hover:bg-[#111114] hover:text-white transition-all flex items-center justify-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                4-Take Director Grid (Batch)
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
