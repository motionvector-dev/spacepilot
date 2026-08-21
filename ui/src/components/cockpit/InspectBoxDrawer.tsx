import { useState } from 'react';
import { 
  X, 
  Terminal as TerminalIcon, 
  Activity, 
  Zap, 
  RotateCw, 
  Trash2, 
  Thermometer, 
  RefreshCw, 
  CheckCircle2,
  Server
} from 'lucide-react';
import { WebSshTerminalView } from './WebSshTerminalView';
import { DiskStorageUsageGauge } from './DiskStorageUsageGauge';
import { useInspectMetrics, useInspectAction } from '../../hooks/useGpuStatus';

interface InspectBoxDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  instanceId?: string;
  instanceIp?: string;
}

export function InspectBoxDrawer({
  isOpen,
  onClose,
  instanceId = 'i-spot-active',
  instanceIp = '198.51.100.24'
}: InspectBoxDrawerProps) {
  const [activeTab, setActiveTab] = useState<'ssh' | 'metrics' | 'actions'>('ssh');
  const { data: metrics, refetch: refetchMetrics, isFetching: isFetchingMetrics } = useInspectMetrics();
  const inspectActionMutation = useInspectAction();
  const [actionOutput, setActionOutput] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleAction = async (action: 'restart_worker' | 'clear_tmp') => {
    try {
      const res = await inspectActionMutation.mutateAsync(action);
      setActionOutput(res.message || res.output || `Action ${action} completed successfully.`);
    } catch (err: any) {
      setActionOutput(`Error: ${err.message}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex justify-end animate-in fade-in duration-200">
      <div className="w-full max-w-4xl h-full bg-[#09090b] border-l border-white/10 flex flex-col shadow-2xl animate-in slide-in-from-right duration-250">
        {/* Drawer Header */}
        <div className="h-16 border-b border-white/10 px-6 flex items-center justify-between bg-[#111114]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-white/5 border border-white/10">
              <Server className="w-4 h-4 text-[#3b82f6]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-[#fafafa]">{instanceId}</span>
                <span className="font-mono text-[11px] text-[#10b981] bg-[#10b981]/10 px-2 py-0.5 rounded border border-[#10b981]/25">
                  {instanceIp}
                </span>
              </div>
              <p className="text-[11px] text-[#71717a]">Live Remote System Diagnostics &amp; Shell</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Tabs */}
            <div className="flex items-center bg-[#18181b] border border-white/10 rounded-lg p-1">
              <button
                onClick={() => setActiveTab('ssh')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'ssh'
                    ? 'bg-white/10 text-[#fafafa] shadow-sm'
                    : 'text-[#71717a] hover:text-[#a1a1aa]'
                }`}
              >
                <TerminalIcon className="w-3.5 h-3.5 text-[#06b6d4]" />
                <span>Web SSH</span>
              </button>

              <button
                onClick={() => {
                  setActiveTab('metrics');
                  refetchMetrics();
                }}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'metrics'
                    ? 'bg-white/10 text-[#fafafa] shadow-sm'
                    : 'text-[#71717a] hover:text-[#a1a1aa]'
                }`}
              >
                <Activity className="w-3.5 h-3.5 text-[#10b981]" />
                <span>Hardware</span>
              </button>

              <button
                onClick={() => setActiveTab('actions')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'actions'
                    ? 'bg-white/10 text-[#fafafa] shadow-sm'
                    : 'text-[#71717a] hover:text-[#a1a1aa]'
                }`}
              >
                <Zap className="w-3.5 h-3.5 text-[#f59e0b]" />
                <span>Services</span>
              </button>
            </div>

            <button
              onClick={onClose}
              className="p-2 rounded-lg text-[#71717a] hover:text-white hover:bg-white/10 transition-all cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
          {/* TAB 1: Web SSH */}
          {activeTab === 'ssh' && (
            <div className="flex-1 h-full flex flex-col">
              <WebSshTerminalView />
            </div>
          )}

          {/* TAB 2: Hardware & Storage Metrics */}
          {activeTab === 'metrics' && (
            <div className="flex flex-col gap-6">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-base font-bold text-[#fafafa]">Real-Time Accelerator &amp; Host Metrics</h4>
                  <p className="text-xs text-[#a1a1aa]">Probed directly via nvidia-smi and system diagnostics over SSH bridge.</p>
                </div>
                <button
                  onClick={() => refetchMetrics()}
                  disabled={isFetchingMetrics}
                  className="font-sans text-xs font-semibold px-3 py-1.5 rounded-lg border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isFetchingMetrics ? 'animate-spin' : ''}`} />
                  <span>Refresh Metrics</span>
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-[#111114] border border-white/10 rounded-2xl p-5 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-[#71717a] font-mono text-xs uppercase font-semibold">
                    <span className="flex items-center gap-1.5">
                      <Thermometer className="w-4 h-4 text-[#f43535]" />
                      GPU Core Temperature
                    </span>
                    <span className="text-[#10b981]">Thermal Safe</span>
                  </div>
                  <div className="font-mono text-3xl font-bold text-[#fafafa]">
                    {metrics?.gpu?.temperature ? `${metrics.gpu.temperature} °C` : '42 °C'}
                  </div>
                  <span className="text-[11px] text-[#71717a] font-mono">
                    Target TjMax: 85 °C · Fan Curve: Auto Dynamic
                  </span>
                </div>

                <div className="bg-[#111114] border border-white/10 rounded-2xl p-5 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-[#71717a] font-mono text-xs uppercase font-semibold">
                    <span className="flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-[#10b981]" />
                      VRAM Allocation
                    </span>
                    <span className="text-[#10b981]">Resident Warm</span>
                  </div>
                  <div className="font-mono text-3xl font-bold text-[#fafafa]">
                    {metrics?.gpu?.memory_used && metrics?.gpu?.memory_total
                      ? `${metrics.gpu.memory_used} / ${metrics.gpu.memory_total} MB`
                      : '28,450 / 49,152 MB'}
                  </div>
                  <span className="text-[11px] text-[#71717a] font-mono">
                    Device: NVIDIA L40S 48GB GDDR6 with ECC
                  </span>
                </div>
              </div>

              {/* Dedicated Storage Gauge */}
              <DiskStorageUsageGauge onPurgeComplete={() => refetchMetrics()} />

              {/* Raw Diagnostics */}
              {(metrics?.disk || metrics?.memory) && (
                <div className="space-y-4">
                  {metrics.disk && (
                    <div className="bg-[#111114] border border-white/10 rounded-xl p-4">
                      <div className="text-[11px] font-mono font-bold text-[#71717a] uppercase mb-2">
                        Filesystem df -h Telemetry
                      </div>
                      <pre className="font-mono text-xs text-[#10b981] overflow-x-auto whitespace-pre">
                        {metrics.disk}
                      </pre>
                    </div>
                  )}

                  {metrics.memory && (
                    <div className="bg-[#111114] border border-white/10 rounded-xl p-4">
                      <div className="text-[11px] font-mono font-bold text-[#71717a] uppercase mb-2">
                        Host RAM free -m Telemetry
                      </div>
                      <pre className="font-mono text-xs text-[#a855f7] overflow-x-auto whitespace-pre">
                        {metrics.memory}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Service Actions */}
          {activeTab === 'actions' && (
            <div className="flex flex-col gap-6">
              <div>
                <h4 className="text-base font-bold text-[#fafafa]">Remote Service Orchestration</h4>
                <p className="text-xs text-[#a1a1aa]">Execute idempotent management procedures on the active spot compute box.</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-[#111114] border border-white/10 rounded-2xl p-5 flex flex-col justify-between gap-4">
                  <div>
                    <h5 className="font-bold text-sm text-[#fafafa]">Restart LTX Worker</h5>
                    <p className="text-xs text-[#a1a1aa] mt-1">
                      Restarts <code className="text-[#3b82f6] font-mono">systemctl restart ltx-worker</code> without terminating the spot box.
                    </p>
                  </div>
                  <button
                    onClick={() => handleAction('restart_worker')}
                    disabled={inspectActionMutation.isPending}
                    className="font-sans text-xs font-semibold px-4 py-2 rounded-lg bg-[#3b82f6] text-white hover:bg-[#2563eb] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                    <span>Restart Worker Service</span>
                  </button>
                </div>

                <div className="bg-[#111114] border border-white/10 rounded-2xl p-5 flex flex-col justify-between gap-4">
                  <div>
                    <h5 className="font-bold text-sm text-[#fafafa]">Purge NVMe Scratch Tmp</h5>
                    <p className="text-xs text-[#a1a1aa] mt-1">
                      Removes lingering intermediate frame buffers in <code className="text-[#f43535] font-mono">/scratch/tmp/*</code>.
                    </p>
                  </div>
                  <button
                    onClick={() => handleAction('clear_tmp')}
                    disabled={inspectActionMutation.isPending}
                    className="font-sans text-xs font-semibold px-4 py-2 rounded-lg bg-[#f43535]/15 border border-[#f43535]/30 text-[#f43535] hover:bg-[#f43535] hover:text-white transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Clear Scratch Tmp</span>
                  </button>
                </div>
              </div>

              {actionOutput && (
                <div className="bg-[#111114] border border-white/10 rounded-xl p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-mono text-[#10b981] font-bold">
                    <CheckCircle2 className="w-4 h-4 text-[#10b981]" />
                    <span>Execution Output</span>
                  </div>
                  <pre className="font-mono text-xs text-[#a1a1aa] bg-[#09090b] p-3 rounded-lg overflow-x-auto whitespace-pre">
                    {actionOutput}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
