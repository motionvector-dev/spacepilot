
import { CockpitHeader } from '../components/cockpit/CockpitHeader';
import { GpuTelemetryGrid } from '../components/cockpit/GpuTelemetryGrid';
import { WebSshTerminalView } from '../components/cockpit/WebSshTerminalView';
import { ModelWeightManager } from '../components/cockpit/ModelWeightManager';
import { LoRAStudioCard } from '../components/cockpit/LoRAStudioCard';
import { Play, Activity, Download, Copy, Trash2 } from 'lucide-react';

export default function CockpitPage() {
  return (
    <main className="max-w-[1120px] mx-auto px-6 py-12 flex flex-col gap-8">
      <CockpitHeader 
        status="online" 
        countdownMinutes={20} 
        onRefresh={() => console.log('Refreshed')} 
      />

      <GpuTelemetryGrid 
        instanceId="i-08a9b8c7d6e5f4g3"
        instanceIp="203.0.113.45"
        instanceType="g6e.xlarge · us-east-1"
        vramUsed={18.4}
        vramTotal={48.0}
        gpuLoad={87}
        costPerHour={0.75}
        totalCost={4.25}
        sessionUptime={340}
        savings={12.50}
      />

      {/* Actions Toolbar */}
      <div className="bg-[#18181b] border border-white/10 rounded-[24px] px-6 py-5 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2.5 flex-wrap">
          <button className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-transparent bg-[#fafafa] text-[#09090b] hover:bg-white transition-all shadow-sm flex items-center gap-2 cursor-pointer">
            <Play className="w-4 h-4" />
            Launch Spot GPU
          </button>
          
          <button className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer">
            <Activity className="w-4 h-4" />
            Deploy Worker
          </button>
          
          <button className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer">
            <Download className="w-4 h-4" />
            Sync Outputs
          </button>
          
          <button className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer">
            <Copy className="w-4 h-4" />
            Copy SSH
          </button>
        </div>

        <button className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-[#f43535]/30 bg-[#f43535]/10 text-[#f43535] hover:bg-[#f43535] hover:text-white transition-all flex items-center gap-2 cursor-pointer">
          <Trash2 className="w-4 h-4" />
          Terminate & Stop Billing
        </button>
      </div>

      <WebSshTerminalView wsUrl="ws://localhost:8080/terminal" />

      <ModelWeightManager />

      <LoRAStudioCard />

    </main>
  );
}
