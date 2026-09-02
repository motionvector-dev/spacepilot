import { useState } from 'react';
import { 
  Globe, 
  Cloud, 
  Zap, 
  Laptop, 
  ShieldCheck, 
  FileCode, 
  Check, 
  RefreshCw, 
  Eye, 
  EyeOff, 
  Settings2,
  X
} from 'lucide-react';
import { 
  useCockpitConfig, 
  useUpdateCockpitConfig, 
  useSkyStatus, 
  useSkyClouds, 
  useSkyFailover, 
  useSkySchedule 
} from '../../hooks/useGpuStatus';
import type { SkyCloudArbitrageItem, SkyYamlResponse } from '../../types/api';

export function MultiCloudProviderHub() {
  const { data: config } = useCockpitConfig();
  const updateConfigMutation = useUpdateCockpitConfig();
  const { data: skyStatus } = useSkyStatus();
  const { data: skyClouds, isLoading: cloudsLoading, error: cloudsError } = useSkyClouds();
  const failoverMutation = useSkyFailover();
  const scheduleMutation = useSkySchedule();

  const [selectedProvider, setSelectedProvider] = useState<'aws' | 'shadeform' | 'runpod' | 'local'>(
    config?.provider || 'aws'
  );
  const [shadeformKey, setShadeformKey] = useState(config?.shadeform_api_key || '');
  const [runpodKey, setRunpodKey] = useState(config?.runpod_api_key || '');
  const [awsProfile, setAwsProfile] = useState(config?.aws_profile || 'default');
  const [localHost, setLocalHost] = useState(config?.local_host || 'http://127.0.0.1:8000');
  
  const [showKey, setShowKey] = useState(false);
  const [savedToast, setSavedToast] = useState(false);
  const [routingProvider, setRoutingProvider] = useState<string | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [failoverError, setFailoverError] = useState<string | null>(null);

  // Modals
  const [showYamlModal, setShowYamlModal] = useState(false);
  const [yamlContent, setYamlContent] = useState('');
  const [yamlLoading, setYamlLoading] = useState(false);
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [showSwitchModal, setShowSwitchModal] = useState(false);

  const clouds = skyClouds ?? [];

  const handleSaveConfig = async () => {
    try {
      await updateConfigMutation.mutateAsync({
        provider: selectedProvider,
        shadeform_api_key: shadeformKey,
        runpod_api_key: runpodKey,
        aws_profile: awsProfile,
        local_host: localHost,
      });
      setSavedToast(true);
      setTimeout(() => setSavedToast(false), 2500);
    } catch {
      // surfaced via updateConfigMutation.isError below
    }
  };

  const handleTriggerFailover = async () => {
    setFailoverError(null);
    try {
      await failoverMutation.mutateAsync('Manual preemption trigger / cloud arbitrage rebalance');
    } catch (err) {
      setFailoverError(err instanceof Error ? err.message : 'Failover failed');
    }
  };

  const handleRouteSpot = async (cloud: SkyCloudArbitrageItem) => {
    setRoutingProvider(cloud.provider);
    setRouteError(null);
    try {
      await scheduleMutation.mutateAsync({
        task_name: `spacepilot-${cloud.provider}-worker`,
        provider: cloud.provider,
        accelerator: cloud.accelerator,
        use_spot: true,
      });
    } catch (err) {
      setRouteError(err instanceof Error ? err.message : `Failed to route ${cloud.name}`);
    } finally {
      setTimeout(() => setRoutingProvider(null), 1500);
    }
  };

  const handleOpenYaml = async () => {
    setShowYamlModal(true);
    setYamlLoading(true);
    setYamlContent('');
    setYamlError(null);
    try {
      // GET /api/sky/yaml carries no require_token dependency (gpu.py) — a
      // read-only spec render, so no X-Pluto-Token is sent here.
      const res = await fetch('/api/sky/yaml?cloud=lambda&accelerators=L40S:1');
      if (!res.ok) throw new Error(`Failed to fetch SkyPilot YAML (${res.status})`);
      const data: SkyYamlResponse = await res.json();
      if (!data.yaml) throw new Error('SkyPilot YAML response was empty');
      setYamlContent(data.yaml);
    } catch (err) {
      setYamlError(err instanceof Error ? err.message : 'Failed to fetch SkyPilot YAML');
    } finally {
      setYamlLoading(false);
    }
  };

  const getRiskBadge = (risk: string, pct: number) => {
    if (risk === 'very-low') {
      return (
        <span className="font-mono text-[11px] font-semibold text-verify bg-verify-soft border border-verify px-2 py-0.5 rounded">
          VERY LOW ({pct}%)
        </span>
      );
    }
    if (risk === 'low') {
      return (
        <span className="font-mono text-[11px] font-semibold text-ink bg-inset border border-line-400 px-2 py-0.5 rounded">
          LOW ({pct}%)
        </span>
      );
    }
    if (risk === 'medium') {
      return (
        <span className="font-mono text-[11px] font-semibold text-ink bg-inset border border-line-400 px-2 py-0.5 rounded">
          MED &middot; WATCH ({pct}%)
        </span>
      );
    }
    return (
      <span className="font-mono text-[11px] font-semibold text-danger bg-danger-soft border border-danger px-2 py-0.5 rounded">
        HIGH ({pct}%)
      </span>
    );
  };

  return (
    <div className="bg-inset border border-line-200 rounded-[24px] p-7 flex flex-col gap-6 hover:border-line-400 transition-all duration-150 ease-in-out">
      {/* 1. Header & Provider Hub Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between pb-5 border-b border-line-200 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-ink-700" />
            <h3 className="text-[18px] font-bold text-ink">
              Multi-Cloud Compute Provider Hub
            </h3>
          </div>
          <p className="text-[13px] text-ink-700 mt-1">
            Intelligent spot arbitrage routing across 12+ cloud providers with instant preemption failover.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <select 
            value={selectedProvider} 
            onChange={(e) => setSelectedProvider(e.target.value as any)}
            className="bg-raised border border-line-300 rounded-lg px-3.5 py-2 text-[13px] font-mono text-ink outline-none focus:border-line-500 transition-all cursor-pointer min-w-[260px]"
          >
            <option value="aws">☁️ AWS Direct Spot (us-east-1 · g6e.xlarge)</option>
            <option value="shadeform">🌐 Shadeform (20+ Clouds · Auto-Cheapest)</option>
            <option value="runpod">🚀 RunPod Serverless / Pods</option>
            <option value="local">💻 Local Homelab / Apple Silicon</option>
          </select>

          <button
            onClick={() => setShowSwitchModal(true)}
            className="font-sans text-xs font-semibold px-3 py-2 rounded-lg border border-line-300 bg-raised text-ink hover:bg-strong transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <Settings2 className="w-3.5 h-3.5 text-ink-700" />
            <span>Connect Hub</span>
          </button>
        </div>
      </div>

      {/* 2. Provider Credentials & Settings Inline Strip */}
      <div className="bg-raised border border-line-200 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {selectedProvider === 'aws' && (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-ink-500">
                  AWS Profile
                </label>
                <input 
                  type="text" 
                  value={awsProfile} 
                  onChange={(e) => setAwsProfile(e.target.value)} 
                  placeholder="default"
                  className="bg-inset border border-line-200 rounded-md px-3 py-1.5 text-xs text-ink font-mono outline-none focus:border-line-500"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-ink-500">
                  Spot Instance Type
                </label>
                <input 
                  type="text" 
                  disabled
                  value="g6e.xlarge (L40S 48GB · $0.75/hr)" 
                  className="bg-inset border border-line-200 rounded-md px-3 py-1.5 text-xs text-ink-700 font-mono cursor-not-allowed opacity-80"
                />
              </div>
            </>
          )}

          {selectedProvider === 'shadeform' && (
            <>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-ink-500 flex items-center justify-between">
                  <span>Shadeform API Key</span>
                  <button onClick={() => setShowKey(!showKey)} className="text-ink-700 text-[10px] lowercase flex items-center gap-1 cursor-pointer">
                    {showKey ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {showKey ? 'hide' : 'reveal'}
                  </button>
                </label>
                <div className="relative">
                  <input 
                    type={showKey ? 'text' : 'password'} 
                    value={shadeformKey} 
                    onChange={(e) => setShadeformKey(e.target.value)} 
                    placeholder="sf_live_..."
                    className="w-full bg-inset border border-line-200 rounded-md px-3 py-1.5 text-xs text-ink font-mono outline-none focus:border-line-500"
                  />
                </div>
              </div>
            </>
          )}

          {selectedProvider === 'runpod' && (
            <>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-ink-500">
                  RunPod API Key
                </label>
                <input 
                  type={showKey ? 'text' : 'password'} 
                  value={runpodKey} 
                  onChange={(e) => setRunpodKey(e.target.value)} 
                  placeholder="rpa_..."
                  className="bg-inset border border-line-200 rounded-md px-3 py-1.5 text-xs text-ink font-mono outline-none focus:border-line-500"
                />
              </div>
            </>
          )}

          {selectedProvider === 'local' && (
            <>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-ink-500">
                  Local Inference Bridge URL
                </label>
                <input 
                  type="text" 
                  value={localHost} 
                  onChange={(e) => setLocalHost(e.target.value)} 
                  placeholder="http://127.0.0.1:8000"
                  className="bg-inset border border-line-200 rounded-md px-3 py-1.5 text-xs text-ink font-mono outline-none focus:border-line-500"
                />
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <button
            onClick={handleSaveConfig}
            disabled={updateConfigMutation.isPending}
            className="font-sans text-xs font-semibold px-4 py-2 rounded-md bg-ink text-ground hover:brightness-110 transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {updateConfigMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            <span>{savedToast ? 'Saved ✓' : 'Save Config'}</span>
          </button>
          {updateConfigMutation.isError && (
            <span className="font-mono text-[11px] text-danger">
              {updateConfigMutation.error instanceof Error ? updateConfigMutation.error.message : 'Save failed'}
            </span>
          )}
        </div>
      </div>

      {/* 3. SkyPilot Cluster Status & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-[13px] font-semibold text-ink">
            SkyPilot Cluster Status:
          </span>
          <span className="font-mono text-xs text-ink-700">
            {skyStatus?.cluster_name ? `${skyStatus.cluster_name} (${skyStatus.provider})` : 'Auto-Arbitrage Mode'}
          </span>
          <span className="font-mono text-[11px] text-verify bg-verify-soft border border-verify px-2 py-0.5 rounded flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-verify animate-pulse" />
            <span>R2 Checkpoint Synced</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleTriggerFailover}
            disabled={failoverMutation.isPending}
            className="font-sans text-xs font-semibold px-3 py-1.5 rounded-md border border-line-400 bg-inset text-ink hover:bg-strong transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {failoverMutation.isPending ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
            <span>⚡ Trigger Failover (Interrupts)</span>
          </button>
          {failoverError && (
            <span className="font-mono text-[11px] text-danger">{failoverError}</span>
          )}

          <button
            onClick={handleOpenYaml}
            className="font-sans text-xs font-semibold px-3 py-1.5 rounded-md border border-line-300 bg-inset text-ink hover:bg-strong transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <FileCode className="w-3.5 h-3.5 text-ink-700" />
            <span>📄 SkyPilot YAML</span>
          </button>
        </div>
      </div>

      {/* 4. Live Spot Arbitrage Matrix Table */}
      {routeError && (
        <div className="font-mono text-[11px] text-danger">{routeError}</div>
      )}
      <div className="overflow-x-auto border border-line-200 rounded-xl bg-surface">
        <table className="w-full border-collapse text-left font-mono text-[12px]">
          <thead>
            <tr className="bg-raised border-b border-line-200 text-ink-700 font-semibold text-[11px]">
              <th className="p-3">Provider</th>
              <th className="p-3">GPU Accelerator</th>
              <th className="p-3">VRAM</th>
              <th className="p-3">Spot / Hr</th>
              <th className="p-3">On-Demand</th>
              <th className="p-3">Preemption Risk</th>
              <th className="p-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {cloudsLoading ? (
              <tr>
                <td colSpan={7} className="p-6 text-center text-ink-700">
                  <div className="flex items-center justify-center gap-2">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Loading spot arbitrage matrix...</span>
                  </div>
                </td>
              </tr>
            ) : cloudsError ? (
              <tr>
                <td colSpan={7} className="p-6 text-center text-danger">
                  {cloudsError instanceof Error ? cloudsError.message : 'Failed to load spot arbitrage matrix'}
                </td>
              </tr>
            ) : clouds.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-6 text-center text-ink-500">
                  No cloud providers reported by the arbitrage matrix.
                </td>
              </tr>
            ) : (
              clouds.map((cloud) => (
                <tr
                  key={`${cloud.provider}-${cloud.accelerator}`}
                  className="border-b border-line-200 last:border-0 hover:bg-raised-hover transition-colors"
                >
                  <td className="p-3 font-semibold text-ink">
                    <div className="flex items-center gap-2">
                      <span>{cloud.name}</span>
                      {cloud.is_cheapest && (
                        <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-verify-soft text-verify border border-verify">
                          Cheapest
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="p-3 text-ink-700">{cloud.accelerator}</td>
                  <td className="p-3 text-ink-500">{cloud.vram_gb} GB</td>
                  <td className="p-3 font-bold text-verify">
                    ${cloud.spot_price_usd.toFixed(2)}
                  </td>
                  <td className="p-3 text-ink-500 line-through">
                    ${cloud.ondemand_price_usd.toFixed(2)}
                  </td>
                  <td className="p-3">
                    {getRiskBadge(cloud.preemption_risk, cloud.preemption_rate_pct)}
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => handleRouteSpot(cloud)}
                      disabled={routingProvider === cloud.provider}
                      className="font-sans text-xs font-semibold px-3 py-1 rounded bg-inset border border-line-300 text-ink hover:bg-strong hover:border-line-400 transition-all cursor-pointer disabled:opacity-50"
                    >
                      {routingProvider === cloud.provider ? 'Routing...' : 'Route'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* YAML Viewer Modal */}
      {showYamlModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface border border-line-300 rounded-2xl w-full max-w-2xl overflow-hidden shadow-lg flex flex-col max-h-[85vh]">
            <div className="px-5 py-3.5 bg-raised border-b border-line-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-ink-700" />
                <span className="font-mono text-sm font-bold text-ink">
                  infra/skypilot.yaml · Declarative Spec
                </span>
              </div>
              <button 
                onClick={() => setShowYamlModal(false)}
                className="p-1 rounded text-ink-700 hover:text-ink transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto font-mono text-xs text-ink-700 leading-relaxed bg-ground">
              {yamlLoading ? (
                <div className="py-12 flex items-center justify-center gap-2 text-ink-700">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating SkyPilot YAML spec...</span>
                </div>
              ) : yamlError ? (
                <div className="py-12 text-center text-danger">{yamlError}</div>
              ) : (
                <pre className="whitespace-pre text-verify">{yamlContent}</pre>
              )}
            </div>

            <div className="px-5 py-3 bg-raised border-t border-line-200 flex items-center justify-between">
              <span className="text-[11px] font-mono text-ink-500">
                Zero-data-loss checkpoint recovery enabled
              </span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(yamlContent);
                  setShowYamlModal(false);
                }}
                disabled={yamlLoading || !!yamlError || !yamlContent}
                className="font-sans text-xs font-semibold px-4 py-1.5 rounded-md bg-ink text-ground hover:brightness-110 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Copy YAML
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Provider Switcher Hub Modal */}
      {showSwitchModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-surface border border-line-300 rounded-3xl w-full max-w-xl p-6 shadow-lg flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-ink">Connect Compute Provider</h3>
                <p className="text-xs text-ink-700 mt-0.5">Select and authorize your primary spot infrastructure backend.</p>
              </div>
              <button 
                onClick={() => setShowSwitchModal(false)}
                className="p-1.5 rounded-lg text-ink-500 hover:text-ink hover:bg-raised-hover transition-all cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {[
                { id: 'aws', name: 'AWS Direct Spot', icon: Cloud, desc: 'g6e/g5 L40S 48GB' },
                { id: 'shadeform', name: 'Shadeform Matrix', icon: Globe, desc: '20+ Clouds Auto-Cheapest' },
                { id: 'runpod', name: 'RunPod Serverless', icon: Zap, desc: 'RTX 4090 / L40S' },
                { id: 'local', name: 'Local Homelab', icon: Laptop, desc: 'Apple MPS / NVIDIA CUDA' },
              ].map(p => (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelectedProvider(p.id as any);
                  }}
                  className={`p-4 rounded-2xl border text-left transition-all cursor-pointer flex flex-col gap-2 ${
                    selectedProvider === p.id 
                      ? 'bg-strong border-line-500' 
                      : 'bg-raised border-line-200 hover:border-line-400'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p.icon className={`w-5 h-5 ${selectedProvider === p.id ? 'text-ink' : 'text-ink-700'}`} />
                    {selectedProvider === p.id && <ShieldCheck className="w-4 h-4 text-ink" />}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-ink">{p.name}</div>
                    <div className="text-[11px] font-mono text-ink-500 mt-0.5">{p.desc}</div>
                  </div>
                </button>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowSwitchModal(false)}
                className="font-sans text-xs font-semibold px-4 py-2 rounded-lg border border-line-200 text-ink-700 hover:bg-raised-hover cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleSaveConfig();
                  setShowSwitchModal(false);
                }}
                className="font-sans text-xs font-semibold px-4 py-2 rounded-lg bg-ink text-ground hover:brightness-110 cursor-pointer"
              >
                Confirm Provider
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
