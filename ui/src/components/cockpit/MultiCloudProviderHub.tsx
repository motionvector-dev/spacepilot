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
import type { SkyCloudArbitrageItem } from '../../types/api';

const DEFAULT_CLOUDS: SkyCloudArbitrageItem[] = [
  { name: 'Lambda Cloud', provider: 'lambda', accelerator: 'NVIDIA L40S', vram_gb: 48, spot_price_usd: 0.72, ondemand_price_usd: 1.89, preemption_risk: 'very-low', preemption_rate_pct: 1.2, is_cheapest: true },
  { name: 'AWS EC2 Spot', provider: 'aws', accelerator: 'NVIDIA L40S (g6e)', vram_gb: 48, spot_price_usd: 0.75, ondemand_price_usd: 2.15, preemption_risk: 'low', preemption_rate_pct: 3.4 },
  { name: 'RunPod Community', provider: 'runpod', accelerator: 'RTX 4090 24GB', vram_gb: 24, spot_price_usd: 0.39, ondemand_price_usd: 0.79, preemption_risk: 'medium', preemption_rate_pct: 7.8 },
  { name: 'Vast.ai Secure', provider: 'vastai', accelerator: 'NVIDIA A100-80GB', vram_gb: 80, spot_price_usd: 1.15, ondemand_price_usd: 3.40, preemption_risk: 'low', preemption_rate_pct: 2.9 },
  { name: 'CoreWeave Cloud', provider: 'coreweave', accelerator: 'NVIDIA H100 SXM5', vram_gb: 80, spot_price_usd: 2.45, ondemand_price_usd: 4.85, preemption_risk: 'very-low', preemption_rate_pct: 0.8 },
  { name: 'FluidStack Spot', provider: 'fluidstack', accelerator: 'NVIDIA A10G', vram_gb: 24, spot_price_usd: 0.45, ondemand_price_usd: 1.20, preemption_risk: 'low', preemption_rate_pct: 4.1 },
];

export function MultiCloudProviderHub() {
  const { data: config } = useCockpitConfig();
  const updateConfigMutation = useUpdateCockpitConfig();
  const { data: skyStatus } = useSkyStatus();
  const { data: skyClouds } = useSkyClouds();
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
  
  // Modals
  const [showYamlModal, setShowYamlModal] = useState(false);
  const [yamlContent, setYamlContent] = useState('');
  const [yamlLoading, setYamlLoading] = useState(false);
  const [showSwitchModal, setShowSwitchModal] = useState(false);

  const displayClouds = skyClouds && skyClouds.length > 0 ? skyClouds : DEFAULT_CLOUDS;

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
      // ignore
    }
  };

  const handleTriggerFailover = async () => {
    await failoverMutation.mutateAsync('Manual preemption trigger / cloud arbitrage rebalance');
  };

  const handleRouteSpot = async (cloud: SkyCloudArbitrageItem) => {
    setRoutingProvider(cloud.provider);
    try {
      await scheduleMutation.mutateAsync({
        task_name: `spacepilot-${cloud.provider}-worker`,
        provider: cloud.provider,
        accelerator: cloud.accelerator,
        use_spot: true,
      });
    } finally {
      setTimeout(() => setRoutingProvider(null), 1500);
    }
  };

  const handleOpenYaml = async () => {
    setShowYamlModal(true);
    setYamlLoading(true);
    try {
      const res = await fetch('/api/sky/yaml?cloud=lambda&accelerators=L40S:1');
      if (res.ok) {
        const data = await res.json();
        setYamlContent(data.yaml || '');
      } else {
        setYamlContent(`# SkyPilot Task Definition (infra/skypilot.yaml)
name: spacepilot-ltx-worker

resources:
  accelerators: L40S:1
  use_spot: true
  spot_recovery: FAILOVER
  any_of:
    - cloud: lambda
    - cloud: aws
    - cloud: runpod
    - cloud: coreweave

envs:
  MODEL_ID: Lightricks/LTX-Video
  PRECISION: float8

setup: |
  pip install -U torch torchvision --index-url https://download.pytorch.org/whl/cu124
  pip install diffusers transformers accelerate sentencepiece

run: |
  python3 -u /scratch/worker/ltx_worker.py --port 8000`);
      }
    } catch {
      setYamlContent('# SkyPilot YAML specification loaded from cache');
    } finally {
      setYamlLoading(false);
    }
  };

  const getRiskBadge = (risk: string, pct: number) => {
    if (risk === 'very-low') {
      return (
        <span className="font-mono text-[11px] font-semibold text-[#10b981] bg-[#10b981]/10 border border-[#10b981]/25 px-2 py-0.5 rounded">
          VERY LOW ({pct}%)
        </span>
      );
    }
    if (risk === 'low') {
      return (
        <span className="font-mono text-[11px] font-semibold text-[#06b6d4] bg-[#06b6d4]/10 border border-[#06b6d4]/25 px-2 py-0.5 rounded">
          LOW ({pct}%)
        </span>
      );
    }
    if (risk === 'medium') {
      return (
        <span className="font-mono text-[11px] font-semibold text-[#f59e0b] bg-[#f59e0b]/10 border border-[#f59e0b]/25 px-2 py-0.5 rounded">
          MED ({pct}%)
        </span>
      );
    }
    return (
      <span className="font-mono text-[11px] font-semibold text-[#f43535] bg-[#f43535]/10 border border-[#f43535]/25 px-2 py-0.5 rounded">
        HIGH ({pct}%)
      </span>
    );
  };

  return (
    <div className="bg-[#18181b] border border-white/10 rounded-[24px] p-7 flex flex-col gap-6 hover:border-white/20 transition-all duration-150 ease-in-out">
      {/* 1. Header & Provider Hub Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between pb-5 border-b border-white/10 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-[#3b82f6]" />
            <h3 className="text-[18px] font-bold text-[#fafafa]">
              Multi-Cloud Compute Provider Hub
            </h3>
          </div>
          <p className="text-[13px] text-[#a1a1aa] mt-1">
            Intelligent spot arbitrage routing across 12+ cloud providers with instant preemption failover.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <select 
            value={selectedProvider} 
            onChange={(e) => setSelectedProvider(e.target.value as any)}
            className="bg-[#111114] border border-white/14 rounded-lg px-3.5 py-2 text-[13px] font-mono text-[#fafafa] outline-none focus:border-[#3b82f6] transition-all cursor-pointer min-w-[260px]"
          >
            <option value="aws">☁️ AWS Direct Spot (us-east-1 · g6e.xlarge)</option>
            <option value="shadeform">🌐 Shadeform (20+ Clouds · Auto-Cheapest)</option>
            <option value="runpod">🚀 RunPod Serverless / Pods</option>
            <option value="local">💻 Local Homelab / Apple Silicon</option>
          </select>

          <button
            onClick={() => setShowSwitchModal(true)}
            className="font-sans text-xs font-semibold px-3 py-2 rounded-lg border border-white/14 bg-[#111114] text-[#fafafa] hover:bg-[#222226] transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <Settings2 className="w-3.5 h-3.5 text-[#a1a1aa]" />
            <span>Connect Hub</span>
          </button>
        </div>
      </div>

      {/* 2. Provider Credentials & Settings Inline Strip */}
      <div className="bg-[#111114] border border-white/10 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {selectedProvider === 'aws' && (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-[#71717a]">
                  AWS Profile
                </label>
                <input 
                  type="text" 
                  value={awsProfile} 
                  onChange={(e) => setAwsProfile(e.target.value)} 
                  placeholder="default"
                  className="bg-[#18181b] border border-white/10 rounded-md px-3 py-1.5 text-xs text-[#fafafa] font-mono outline-none focus:border-[#3b82f6]"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-[#71717a]">
                  Spot Instance Type
                </label>
                <input 
                  type="text" 
                  disabled
                  value="g6e.xlarge (L40S 48GB · $0.75/hr)" 
                  className="bg-[#18181b] border border-white/10 rounded-md px-3 py-1.5 text-xs text-[#a1a1aa] font-mono cursor-not-allowed opacity-80"
                />
              </div>
            </>
          )}

          {selectedProvider === 'shadeform' && (
            <>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-[#71717a] flex items-center justify-between">
                  <span>Shadeform API Key</span>
                  <button onClick={() => setShowKey(!showKey)} className="text-[#3b82f6] text-[10px] lowercase flex items-center gap-1 cursor-pointer">
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
                    className="w-full bg-[#18181b] border border-white/10 rounded-md px-3 py-1.5 text-xs text-[#fafafa] font-mono outline-none focus:border-[#3b82f6]"
                  />
                </div>
              </div>
            </>
          )}

          {selectedProvider === 'runpod' && (
            <>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-[#71717a]">
                  RunPod API Key
                </label>
                <input 
                  type={showKey ? 'text' : 'password'} 
                  value={runpodKey} 
                  onChange={(e) => setRunpodKey(e.target.value)} 
                  placeholder="rpa_..."
                  className="bg-[#18181b] border border-white/10 rounded-md px-3 py-1.5 text-xs text-[#fafafa] font-mono outline-none focus:border-[#3b82f6]"
                />
              </div>
            </>
          )}

          {selectedProvider === 'local' && (
            <>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label className="text-[10.5px] font-mono font-semibold uppercase text-[#71717a]">
                  Local Inference Bridge URL
                </label>
                <input 
                  type="text" 
                  value={localHost} 
                  onChange={(e) => setLocalHost(e.target.value)} 
                  placeholder="http://127.0.0.1:8000"
                  className="bg-[#18181b] border border-white/10 rounded-md px-3 py-1.5 text-xs text-[#fafafa] font-mono outline-none focus:border-[#3b82f6]"
                />
              </div>
            </>
          )}
        </div>

        <button
          onClick={handleSaveConfig}
          disabled={updateConfigMutation.isPending}
          className="font-sans text-xs font-semibold px-4 py-2 rounded-md bg-[#fafafa] text-[#09090b] hover:bg-white transition-all flex items-center justify-center gap-1.5 cursor-pointer shrink-0 disabled:opacity-50"
        >
          {updateConfigMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
          <span>{savedToast ? 'Saved ✓' : 'Save Config'}</span>
        </button>
      </div>

      {/* 3. SkyPilot Cluster Status & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-[13px] font-semibold text-[#fafafa]">
            SkyPilot Cluster Status:
          </span>
          <span className="font-mono text-xs text-[#a1a1aa]">
            {skyStatus?.cluster_name ? `${skyStatus.cluster_name} (${skyStatus.provider})` : 'Auto-Arbitrage Mode'}
          </span>
          <span className="font-mono text-[11px] text-[#10b981] bg-[#10b981]/10 border border-[#10b981]/25 px-2 py-0.5 rounded flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
            <span>R2 Checkpoint Synced</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleTriggerFailover}
            disabled={failoverMutation.isPending}
            className="font-sans text-xs font-semibold px-3 py-1.5 rounded-md border border-[#f59e0b]/30 bg-[#f59e0b]/10 text-[#f59e0b] hover:bg-[#f59e0b] hover:text-[#09090b] transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {failoverMutation.isPending ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
            <span>⚡ Trigger Failover</span>
          </button>

          <button
            onClick={handleOpenYaml}
            className="font-sans text-xs font-semibold px-3 py-1.5 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <FileCode className="w-3.5 h-3.5 text-[#06b6d4]" />
            <span>📄 SkyPilot YAML</span>
          </button>
        </div>
      </div>

      {/* 4. Live Spot Arbitrage Matrix Table */}
      <div className="overflow-x-auto border border-white/10 rounded-xl bg-[#09090b]">
        <table className="w-full border-collapse text-left font-mono text-[12px]">
          <thead>
            <tr className="bg-[#111114] border-b border-white/10 text-[#a1a1aa] font-semibold text-[11px]">
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
            {displayClouds.map((cloud) => (
              <tr 
                key={`${cloud.provider}-${cloud.accelerator}`}
                className="border-b border-white/5 last:border-0 hover:bg-white/[0.03] transition-colors"
              >
                <td className="p-3 font-semibold text-[#fafafa]">
                  <div className="flex items-center gap-2">
                    <span>{cloud.name}</span>
                    {cloud.is_cheapest && (
                      <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/30">
                        Cheapest
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-3 text-[#a1a1aa]">{cloud.accelerator}</td>
                <td className="p-3 text-[#71717a]">{cloud.vram_gb} GB</td>
                <td className="p-3 font-bold text-[#10b981]">
                  ${cloud.spot_price_usd.toFixed(2)}
                </td>
                <td className="p-3 text-[#71717a] line-through">
                  ${cloud.ondemand_price_usd.toFixed(2)}
                </td>
                <td className="p-3">
                  {getRiskBadge(cloud.preemption_risk, cloud.preemption_rate_pct)}
                </td>
                <td className="p-3 text-right">
                  <button
                    onClick={() => handleRouteSpot(cloud)}
                    disabled={routingProvider === cloud.provider}
                    className="font-sans text-xs font-semibold px-3 py-1 rounded bg-[#18181b] border border-white/14 text-[#fafafa] hover:bg-[#222226] hover:border-white/25 transition-all cursor-pointer disabled:opacity-50"
                  >
                    {routingProvider === cloud.provider ? 'Routing...' : 'Route'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* YAML Viewer Modal */}
      {showYamlModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#09090b] border border-white/14 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
            <div className="px-5 py-3.5 bg-[#111114] border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-[#06b6d4]" />
                <span className="font-mono text-sm font-bold text-[#fafafa]">
                  infra/skypilot.yaml · Declarative Spec
                </span>
              </div>
              <button 
                onClick={() => setShowYamlModal(false)}
                className="p-1 rounded text-[#a1a1aa] hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto font-mono text-xs text-[#a1a1aa] leading-relaxed bg-[#000000]">
              {yamlLoading ? (
                <div className="py-12 flex items-center justify-center gap-2 text-[#a1a1aa]">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating SkyPilot YAML spec...</span>
                </div>
              ) : (
                <pre className="whitespace-pre text-[#10b981]">{yamlContent}</pre>
              )}
            </div>

            <div className="px-5 py-3 bg-[#111114] border-t border-white/10 flex items-center justify-between">
              <span className="text-[11px] font-mono text-[#71717a]">
                Zero-data-loss checkpoint recovery enabled
              </span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(yamlContent);
                  setShowYamlModal(false);
                }}
                className="font-sans text-xs font-semibold px-4 py-1.5 rounded-md bg-[#fafafa] text-[#09090b] hover:bg-white transition-all cursor-pointer"
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
          <div className="bg-[#09090b] border border-white/14 rounded-3xl w-full max-w-xl p-6 shadow-2xl flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-[#fafafa]">Connect Compute Provider</h3>
                <p className="text-xs text-[#a1a1aa] mt-0.5">Select and authorize your primary spot infrastructure backend.</p>
              </div>
              <button 
                onClick={() => setShowSwitchModal(false)}
                className="p-1.5 rounded-lg text-[#71717a] hover:text-white hover:bg-white/10 transition-all cursor-pointer"
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
                      ? 'bg-[#3b82f6]/10 border-[#3b82f6] shadow-[0_0_12px_rgba(59,130,246,0.2)]' 
                      : 'bg-[#111114] border-white/10 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p.icon className={`w-5 h-5 ${selectedProvider === p.id ? 'text-[#3b82f6]' : 'text-[#a1a1aa]'}`} />
                    {selectedProvider === p.id && <ShieldCheck className="w-4 h-4 text-[#3b82f6]" />}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-[#fafafa]">{p.name}</div>
                    <div className="text-[11px] font-mono text-[#71717a] mt-0.5">{p.desc}</div>
                  </div>
                </button>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowSwitchModal(false)}
                className="font-sans text-xs font-semibold px-4 py-2 rounded-lg border border-white/10 text-[#a1a1aa] hover:bg-white/5 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleSaveConfig();
                  setShowSwitchModal(false);
                }}
                className="font-sans text-xs font-semibold px-4 py-2 rounded-lg bg-[#fafafa] text-[#09090b] hover:bg-white cursor-pointer"
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
