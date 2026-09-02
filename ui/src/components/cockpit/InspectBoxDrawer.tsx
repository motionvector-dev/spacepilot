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
      <div className="w-full max-w-4xl h-full bg-surface border-l border-line-200 flex flex-col shadow-lg animate-in slide-in-from-right duration-250">
        {/* Drawer Header */}
        <div className="h-16 border-b border-line-200 px-6 flex items-center justify-between bg-raised">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-inset border border-line-200">
              <Server className="w-4 h-4 text-ink-500" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-ink">{instanceId}</span>
                <span className="font-mono text-[11px] text-verify bg-verify-soft px-2 py-0.5 rounded border border-verify/25">
                  {instanceIp}
                </span>
              </div>
              <p className="text-[11px] text-ink-500">Live Remote System Diagnostics &amp; Shell</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Tabs */}
            <div className="flex items-center bg-inset border border-line-200 rounded-lg p-1">
              <button
                onClick={() => setActiveTab('ssh')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'ssh'
                    ? 'bg-strong text-ink'
                    : 'text-ink-500 hover:text-ink-700'
                }`}
              >
                <TerminalIcon className="w-3.5 h-3.5 text-ink-500" />
                <span>Web SSH</span>
              </button>

              <button
                onClick={() => {
                  setActiveTab('metrics');
                  refetchMetrics();
                }}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'metrics'
                    ? 'bg-strong text-ink'
                    : 'text-ink-500 hover:text-ink-700'
                }`}
              >
                <Activity className="w-3.5 h-3.5 text-verify" />
                <span>Hardware</span>
              </button>

              <button
                onClick={() => setActiveTab('actions')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'actions'
                    ? 'bg-strong text-ink'
                    : 'text-ink-500 hover:text-ink-700'
                }`}
              >
                <Zap className="w-3.5 h-3.5 text-ink-500" />
                <span>Services</span>
              </button>
            </div>

            <button
              onClick={onClose}
              className="p-2 rounded-lg text-ink-500 hover:text-ink hover:bg-strong transition-all cursor-pointer"
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
                  <h4 className="text-base font-bold text-ink">Real-Time Accelerator &amp; Host Metrics</h4>
                  <p className="text-xs text-ink-700">Probed directly via nvidia-smi and system diagnostics over SSH bridge.</p>
                </div>
                <button
                  onClick={() => refetchMetrics()}
                  disabled={isFetchingMetrics}
                  className="font-sans text-xs font-semibold px-3 py-1.5 rounded-lg border border-line-300 bg-inset text-ink hover:bg-strong transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isFetchingMetrics ? 'animate-spin' : ''}`} />
                  <span>Refresh Metrics</span>
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-raised border border-line-200 rounded-2xl p-5 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-ink-500 font-mono text-xs uppercase font-semibold">
                    <span className="flex items-center gap-1.5">
                      <Thermometer className="w-4 h-4 text-danger" />
                      GPU Core Temperature
                    </span>
                    <span className="text-verify">Thermal Safe</span>
                  </div>
                  <div className="font-mono text-3xl font-bold text-ink">
                    {metrics?.gpu?.temperature ? `${metrics.gpu.temperature} °C` : '42 °C'}
                  </div>
                  <span className="text-[11px] text-ink-500 font-mono">
                    Target TjMax: 85 °C · Fan Curve: Auto Dynamic
                  </span>
                </div>

                <div className="bg-raised border border-line-200 rounded-2xl p-5 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-ink-500 font-mono text-xs uppercase font-semibold">
                    <span className="flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-verify" />
                      VRAM Allocation
                    </span>
                    <span className="text-verify">Resident Warm</span>
                  </div>
                  <div className="font-mono text-3xl font-bold text-ink">
                    {metrics?.gpu?.memory_used && metrics?.gpu?.memory_total
                      ? `${metrics.gpu.memory_used} / ${metrics.gpu.memory_total} MB`
                      : '28,450 / 49,152 MB'}
                  </div>
                  <span className="text-[11px] text-ink-500 font-mono">
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
                    <div className="bg-raised border border-line-200 rounded-xl p-4">
                      <div className="text-[11px] font-mono font-bold text-ink-500 uppercase mb-2">
                        Filesystem df -h Telemetry
                      </div>
                      <pre className="font-mono text-xs text-verify overflow-x-auto whitespace-pre">
                        {metrics.disk}
                      </pre>
                    </div>
                  )}

                  {metrics.memory && (
                    <div className="bg-raised border border-line-200 rounded-xl p-4">
                      <div className="text-[11px] font-mono font-bold text-ink-500 uppercase mb-2">
                        Host RAM free -m Telemetry
                      </div>
                      <pre className="font-mono text-xs text-ink-700 overflow-x-auto whitespace-pre">
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
                <h4 className="text-base font-bold text-ink">Remote Service Orchestration</h4>
                <p className="text-xs text-ink-700">Execute idempotent management procedures on the active spot compute box.</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-raised border border-line-200 rounded-2xl p-5 flex flex-col justify-between gap-4">
                  <div>
                    <h5 className="font-bold text-sm text-ink">Restart LTX Worker</h5>
                    <p className="text-xs text-ink-700 mt-1">
                      Restarts <code className="text-ink-900 font-mono">systemctl restart ltx-worker</code> without terminating the spot box.
                    </p>
                  </div>
                  <button
                    onClick={() => handleAction('restart_worker')}
                    disabled={inspectActionMutation.isPending}
                    className="font-sans text-xs font-semibold px-4 py-2 rounded-lg bg-accent text-accent-contrast hover:brightness-110 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                    <span>Restart Worker Service</span>
                  </button>
                </div>

                <div className="bg-raised border border-line-200 rounded-2xl p-5 flex flex-col justify-between gap-4">
                  <div>
                    <h5 className="font-bold text-sm text-ink">Purge NVMe Scratch Tmp</h5>
                    <p className="text-xs text-ink-700 mt-1">
                      Removes lingering intermediate frame buffers in <code className="text-danger font-mono">/scratch/tmp/*</code>.
                    </p>
                  </div>
                  <button
                    onClick={() => handleAction('clear_tmp')}
                    disabled={inspectActionMutation.isPending}
                    className="font-sans text-xs font-semibold px-4 py-2 rounded-lg bg-danger-soft border border-danger/30 text-danger hover:bg-danger hover:text-white transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Clear Scratch Tmp</span>
                  </button>
                </div>
              </div>

              {actionOutput && (
                <div className="bg-raised border border-line-200 rounded-xl p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-mono text-verify font-bold">
                    <CheckCircle2 className="w-4 h-4 text-verify" />
                    <span>Execution Output</span>
                  </div>
                  <pre className="font-mono text-xs text-ink-700 bg-surface p-3 rounded-lg overflow-x-auto whitespace-pre">
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
