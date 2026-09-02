import { useState } from 'react';
import {
  useCockpitTelemetry,
  useGpuMetrics,
  useCockpitConfig,
  useUpdateCockpitConfig,
  fetchToken,
} from '../hooks/useGpuStatus';
import { CockpitHeader } from '../components/cockpit/CockpitHeader';
import { GpuTelemetryGrid } from '../components/cockpit/GpuTelemetryGrid';
import { DiskStorageUsageGauge } from '../components/cockpit/DiskStorageUsageGauge';
import { MultiCloudProviderHub } from '../components/cockpit/MultiCloudProviderHub';
import { SpotFleetSettingsCard } from '../components/cockpit/SpotFleetSettingsCard';
import { WebSshTerminalView } from '../components/cockpit/WebSshTerminalView';
import { ModelWeightManager } from '../components/cockpit/ModelWeightManager';
import { LoRAStudioCard } from '../components/cockpit/LoRAStudioCard';
import { InspectBoxDrawer } from '../components/cockpit/InspectBoxDrawer';
import { LaunchConfirmationModal } from '../components/cockpit/LaunchConfirmationModal';
import { TerminateConfirmationModal } from '../components/cockpit/TerminateConfirmationModal';
import { Play, RotateCw, Download, Copy, Trash2, AlertTriangle, Check } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';

export default function CockpitPage() {
  const queryClient = useQueryClient();
  const { data: statusData, isError, refetch } = useCockpitTelemetry();
  const { data: metricsData } = useGpuMetrics();
  const { data: configData } = useCockpitConfig();
  const updateConfigMutation = useUpdateCockpitConfig();

  // Modals & Drawers state
  const [isLaunchModalOpen, setIsLaunchModalOpen] = useState(false);
  const [isTerminateModalOpen, setIsTerminateModalOpen] = useState(false);
  const [isInspectDrawerOpen, setIsInspectDrawerOpen] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['cockpit-status'] });
    queryClient.invalidateQueries({ queryKey: ['gpu-metrics'] });
    queryClient.invalidateQueries({ queryKey: ['inspect-metrics'] });
    queryClient.invalidateQueries({ queryKey: ['cockpit-config'] });
    queryClient.invalidateQueries({ queryKey: ['sky-status'] });
    queryClient.invalidateQueries({ queryKey: ['sky-clouds'] });
    queryClient.invalidateQueries({ queryKey: ['compute-profile'] });
    queryClient.invalidateQueries({ queryKey: ['recommended-models'] });
    refetch();
    showToast('Telemetry refreshed');
  };

  // Watchdog Dead Man's Switch Extend Handler
  const handleExtendWatchdog = async (additionalMins: number) => {
    const currentMins = configData?.idle_shutdown_minutes ?? 20;
    const newTimeout = currentMins + additionalMins;
    try {
      await updateConfigMutation.mutateAsync({
        idle_shutdown_minutes: newTimeout,
      });
      showToast(`Watchdog extended by +${additionalMins}m (New timeout: ${newTimeout}m)`);
      queryClient.invalidateQueries({ queryKey: ['cockpit-status'] });
    } catch {
      showToast('Failed to extend watchdog');
    }
  };

  const handleResetWatchdog = async () => {
    try {
      await updateConfigMutation.mutateAsync({
        idle_shutdown_minutes: 20,
      });
      showToast('Watchdog timer reset to 20m default');
      queryClient.invalidateQueries({ queryKey: ['cockpit-status'] });
    } catch {
      showToast('Failed to reset watchdog');
    }
  };

  // gpu.py's launch/terminate/deploy/sync are all gated by Depends(require_token) —
  // every call here needs X-Pluto-Token or the backend 401s.
  const authHeaders = async (): Promise<Record<string, string>> => {
    const token = await fetchToken();
    return token ? { 'X-Pluto-Token': token } : {};
  };

  // Launch Spot GPU with confirmation. gpu.py 400s without {confirm: true} in the body.
  const handleConfirmLaunch = async () => {
    setIsLaunchModalOpen(false);
    try {
      const res = await fetch('/api/gpu/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
        body: JSON.stringify({ confirm: true }),
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || 'GPU instance launch initiated');
        setTimeout(handleRefresh, 2000);
      } else {
        showToast(`Launch failed: ${data.detail || data.message}`);
      }
    } catch (err: any) {
      showToast(`Launch error: ${err.message}`);
    }
  };

  // Terminate Spot GPU with confirmation. Same {confirm: true} requirement as launch.
  const handleConfirmTerminate = async () => {
    setIsTerminateModalOpen(false);
    try {
      const res = await fetch('/api/gpu/terminate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
        body: JSON.stringify({ confirm: true }),
      });
      const data = await res.json();
      if (res.ok) {
        showToast('GPU box terminated cleanly. Billing stopped.');
        handleRefresh();
      } else {
        showToast(`Terminate error: ${data.detail || data.message}`);
      }
    } catch (err: any) {
      showToast(`Terminate error: ${err.message}`);
    }
  };

  // Deploy Worker
  const handleDeployWorker = async () => {
    setIsDeploying(true);
    showToast('Hot-deploying ltx_worker.py to remote GPU box...');
    try {
      const res = await fetch('/api/gpu/deploy', { method: 'POST', headers: await authHeaders() });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || 'Worker deployment initiated in background');
      } else {
        showToast(`Deploy error: ${data.detail || data.message}`);
      }
    } catch (err: any) {
      showToast(`Deploy error: ${err.message}`);
    } finally {
      setTimeout(() => setIsDeploying(false), 2500);
    }
  };

  // Sync Outputs
  const handleSyncOutputs = async () => {
    setIsSyncing(true);
    showToast('Rsyncing /scratch/out/ to local outputs/...');
    try {
      const res = await fetch('/api/gpu/sync', { method: 'POST', headers: await authHeaders() });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || 'Sync complete. All videos downloaded.');
      } else {
        showToast(`Sync error: ${data.detail || data.message}`);
      }
    } catch (err: any) {
      showToast(`Sync error: ${err.message}`);
    } finally {
      setTimeout(() => setIsSyncing(false), 2000);
    }
  };

  // Copy SSH Command
  const handleCopySsh = () => {
    const ip = statusData?.instance?.ip || '198.51.100.24';
    const key = configData?.key_file || '~/.ssh/pluto-gpu-key-2026-07-26.pem';
    const sshCmd = `ssh -i ${key} ubuntu@${ip}`;
    navigator.clipboard.writeText(sshCmd);
    showToast('Copied SSH command to clipboard');
  };

  const isRunning = statusData?.instance?.state === 'running' || statusData?.gpu_online;
  const statusState = isError ? 'offline' : (isRunning ? 'online' : 'connecting');
  const deadManMinutes = Math.max(0, (configData?.idle_shutdown_minutes ?? 20) - (statusData?.watchdog?.elapsed_mins || 0));

  return (
    <main className="max-w-[1120px] mx-auto px-6 py-12 flex flex-col gap-8">
      {/* 1. Header & Dead Man's Switch Watchdog Controls */}
      <CockpitHeader 
        status={statusState}
        countdownMinutes={deadManMinutes}
        onRefresh={handleRefresh}
        onExtendWatchdog={handleExtendWatchdog}
        onResetWatchdog={handleResetWatchdog}
        isExtending={updateConfigMutation.isPending}
      />

      {isError && (
        <div className="bg-[#f43535]/10 border border-[#f43535]/30 rounded-xl p-4 flex items-center gap-3 text-[#f43535] text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <div>
            <span className="font-bold">Backend Standby:</span> Running in high-fidelity mock mode. Live telemetry will synchronize when GPU instance connects.
          </div>
        </div>
      )}

      {/* 2. Telemetry Grid (Instance Compute, VRAM, and Live Billing Odometer) */}
      <GpuTelemetryGrid 
        instanceId={statusData?.instance?.id || 'i-spot-g6e-01'}
        instanceIp={statusData?.instance?.ip || '198.51.100.24'}
        instanceType={statusData?.instance?.type || 'g6e.xlarge · us-east-1'}
        isOnline={Boolean(isRunning)}
        vramUsed={metricsData?.vram_used_mb ? metricsData.vram_used_mb / 1024 : (statusData?.vram_used_gb ?? 18.4)}
        vramTotal={metricsData?.vram_total_mb ? metricsData.vram_total_mb / 1024 : (statusData?.vram_total_gb ?? 48.0)}
        gpuLoad={metricsData?.gpu_utilization_pct ?? (isRunning ? 72 : 0)}
        costPerHour={configData?.spot_hourly_rate || 0.75}
        onDemandRate={1.75}
        initialUptimeMinutes={statusData?.uptime_minutes ?? 18.5}
        onInspect={() => setIsInspectDrawerOpen(true)}
        idleShutdownMins={configData?.idle_shutdown_minutes ?? 20}
      />

      {/* 3. One-Click Command Center Toolbar */}
      <div className="bg-[#18181b] border border-white/10 rounded-[24px] px-6 py-5 flex items-center justify-between gap-4 flex-wrap hover:border-white/20 transition-all">
        <div className="flex items-center gap-2.5 flex-wrap">
          <button 
            onClick={() => setIsLaunchModalOpen(true)}
            disabled={isRunning}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-transparent bg-[#fafafa] text-[#09090b] hover:bg-white transition-all shadow-sm flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Play className="w-4 h-4" />
            <span>Launch Spot GPU</span>
          </button>
          
          <button 
            onClick={handleDeployWorker}
            disabled={!isRunning || isDeploying}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <RotateCw className={`w-4 h-4 text-[#3b82f6] ${isDeploying ? 'animate-spin' : ''}`} />
            <span>{isDeploying ? 'Deploying...' : 'Deploy Worker'}</span>
          </button>
          
          <button 
            onClick={handleSyncOutputs}
            disabled={!isRunning || isSyncing}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Download className={`w-4 h-4 text-[#10b981] ${isSyncing ? 'animate-bounce' : ''}`} />
            <span>{isSyncing ? 'Syncing...' : 'Sync Outputs'}</span>
          </button>
          
          <button 
            onClick={handleCopySsh}
            disabled={!isRunning}
            className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Copy className="w-4 h-4 text-[#06b6d4]" />
            <span>Copy SSH</span>
          </button>
        </div>

        <button 
          onClick={() => setIsTerminateModalOpen(true)}
          disabled={!isRunning}
          className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-[#f43535]/30 bg-[#f43535]/10 text-[#f43535] hover:bg-[#f43535] hover:text-white transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Trash2 className="w-4 h-4" />
          <span>Terminate &amp; Stop Billing</span>
        </button>
      </div>

      {/* 4. Remote Streaming Terminal (Fullscreen, Clear, Font Scaling) */}
      {/* Relative path: WebSshTerminalView derives ws:// vs wss:// and host from window.location.
          A hardcoded ws://127.0.0.1:8088 only works on one specific dev port and breaks in prod. */}
      <WebSshTerminalView
        wsUrl="/api/gpu/inspect/shell"
        streamUrl="/api/gpu/logs/stream"
      />

      {/* 5. Disk Storage Usage Gauge (SSD Root / and NVMe Cache /mnt/pluto-cache) */}
      <DiskStorageUsageGauge 
        rootUsedGb={28.4}
        rootTotalGb={100.0}
        cacheUsedGb={142.5}
        cacheTotalGb={500.0}
        ramUsedGb={18.2}
        ramTotalGb={64.0}
        ioRateMbS={3800}
      />

      {/* 6. Multi-Cloud Compute Provider Hub & SkyPilot Matrix */}
      <MultiCloudProviderHub />

      {/* 7. Host Device Compute & Model Registry */}
      <ModelWeightManager />

      {/* 8. AWS Spot Fleet Settings & Generation Defaults */}
      <SpotFleetSettingsCard />

      {/* 9. PEFT LoRA Studio Adapter Card */}
      <LoRAStudioCard />

      {/* Slide-over Inspect Box Drawer */}
      <InspectBoxDrawer 
        isOpen={isInspectDrawerOpen}
        onClose={() => setIsInspectDrawerOpen(false)}
        instanceId={statusData?.instance?.id || 'i-spot-g6e-01'}
        instanceIp={statusData?.instance?.ip || '198.51.100.24'}
      />

      {/* Launch Confirmation Modal */}
      <LaunchConfirmationModal 
        isOpen={isLaunchModalOpen}
        onClose={() => setIsLaunchModalOpen(false)}
        onConfirm={handleConfirmLaunch}
        instanceType={configData?.instance_type || 'g6e.xlarge'}
        region={configData?.region || 'us-east-1'}
        estimatedRate={configData?.spot_hourly_rate || 0.75}
      />

      {/* Terminate Confirmation Modal */}
      <TerminateConfirmationModal 
        isOpen={isTerminateModalOpen}
        onClose={() => setIsTerminateModalOpen(false)}
        onConfirm={handleConfirmTerminate}
        instanceId={statusData?.instance?.id || 'i-spot-g6e-01'}
        uptimeText={`${statusData?.uptime_minutes ?? 18.5} mins`}
      />

      {/* Toast Notification */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#18181b] border border-white/20 text-[#fafafa] px-4 py-2.5 rounded-xl shadow-2xl font-mono text-xs flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
          <Check className="w-4 h-4 text-[#10b981]" />
          <span>{toastMsg}</span>
        </div>
      )}
    </main>
  );
}

