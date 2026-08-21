import { useCockpitTelemetry, useGpuMetrics } from '../hooks/useGpuStatus';
import { CockpitHeader } from '../components/cockpit/CockpitHeader';
import { GpuTelemetryGrid } from '../components/cockpit/GpuTelemetryGrid';
import { WebSshTerminalView } from '../components/cockpit/WebSshTerminalView';
import { ModelWeightManager } from '../components/cockpit/ModelWeightManager';
import { LoRAStudioCard } from '../components/cockpit/LoRAStudioCard';
import { Play, Activity, Download, Copy, Trash2, AlertTriangle } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';

export default function CockpitPage() {
  const queryClient = useQueryClient();
  const { data: statusData, isError, refetch } = useCockpitTelemetry();
  const { data: metricsData } = useGpuMetrics();

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['cockpit-status'] });
    queryClient.invalidateQueries({ queryKey: ['gpu-metrics'] });
    queryClient.invalidateQueries({ queryKey: ['compute-profile'] });
    queryClient.invalidateQueries({ queryKey: ['recommended-models'] });
    refetch();
  };

  const handleTerminate = async () => {
    try {
      const res = await fetch('/api/sky/terminate', { method: 'POST' });
      if (res.ok) {
        handleRefresh();
      }
    } catch {
      // ignore
    }
  };

  const handleLaunch = async () => {
    try {
      const res = await fetch('/api/sky/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instance_type: 'g6e.xlarge', provider: 'aws_spot' })
      });
      if (res.ok) {
        handleRefresh();
      }
    } catch {
      // ignore
    }
  };

  const statusState = isError ? 'offline' : (statusData?.gpu_online ? 'online' : 'connecting');
  const deadManMinutes = Math.max(0, 30 - (statusData?.watchdog?.elapsed_mins || 0));

  return (
    <main className="max-w-[1120px] mx-auto px-6 py-12 flex flex-col gap-8">
      <CockpitHeader 
        status={statusState}
        countdownMinutes={deadManMinutes}
        onRefresh={handleRefresh} 
      />

      {isError && (
        <div className="bg-[#f43535]/10 border border-[#f43535]/30 rounded-xl p-4 flex items-center gap-3 text-[#f43535] text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <div>
            <span className="font-bold">Backend Offline:</span> Unable to connect to SpacePilot API on port 8088. Showing cached telemetry.
          </div>
        </div>
      )}

      <GpuTelemetryGrid 
        instanceId={statusData?.instance?.id || 'i-spot-local'}
        instanceIp={statusData?.instance?.ip || '127.0.0.1'}
        instanceType={statusData?.instance?.type || 'g6e.xlarge · us-east-1'}
        vramUsed={metricsData?.vram_used_mb ? metricsData.vram_used_mb / 1024 : (statusData?.vram_used_gb ?? 18.4)}
        vramTotal={metricsData?.vram_total_mb ? metricsData.vram_total_mb / 1024 : (statusData?.vram_total_gb ?? 48.0)}
        gpuLoad={metricsData?.gpu_utilization_pct ?? (statusData?.gpu_online ? 72 : 0)}
        costPerHour={0.75}
        totalCost={statusData?.estimated_cost_usd ?? 0.00}
        sessionUptime={statusData?.uptime_minutes ?? 0}
        savings={((statusData?.uptime_minutes ?? 0) / 60) * 1.75}
      />

      {/* Actions Toolbar */}
      <div className="bg-[#18181b] border border-white/10 rounded-[24px] px-6 py-5 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2.5 flex-wrap">
          <button 
            onClick={handleLaunch}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-transparent bg-[#fafafa] text-[#09090b] hover:bg-white transition-all shadow-sm flex items-center gap-2 cursor-pointer"
          >
            <Play className="w-4 h-4" />
            Launch Spot GPU
          </button>
          
          <button 
            onClick={handleRefresh}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer"
          >
            <Activity className="w-4 h-4" />
            Ping Hardware
          </button>
          
          <button 
            onClick={() => {
              window.open('/api/assets', '_blank');
            }}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer"
          >
            <Download className="w-4 h-4" />
            Sync Outputs
          </button>
          
          <button 
            onClick={() => {
              navigator.clipboard.writeText(`ssh spacepilot@${statusData?.instance?.ip || '127.0.0.1'}`);
            }}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer"
          >
            <Copy className="w-4 h-4" />
            Copy SSH
          </button>
        </div>

        <button 
          onClick={handleTerminate}
          className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-[#f43535]/30 bg-[#f43535]/10 text-[#f43535] hover:bg-[#f43535] hover:text-white transition-all flex items-center gap-2 cursor-pointer"
        >
          <Trash2 className="w-4 h-4" />
          Terminate & Stop Billing
        </button>
      </div>

      <WebSshTerminalView wsUrl="ws://127.0.0.1:8088/api/gpu/inspect/shell" />

      <ModelWeightManager />

      <LoRAStudioCard />

    </main>
  );
}
