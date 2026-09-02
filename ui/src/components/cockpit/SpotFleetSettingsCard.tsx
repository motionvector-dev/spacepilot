import { useState, useEffect } from 'react';
import { Sliders, Key, ShieldAlert, Check, RefreshCw, Layers } from 'lucide-react';
import { useCockpitConfig, useUpdateCockpitConfig } from '../../hooks/useGpuStatus';

export function SpotFleetSettingsCard() {
  const { data: config } = useCockpitConfig();
  const updateConfigMutation = useUpdateCockpitConfig();

  const [region, setRegion] = useState(config?.region || 'us-east-1');
  const [instanceType, setInstanceType] = useState(config?.instance_type || 'g6e.xlarge');
  const [idleShutdown, setIdleShutdown] = useState<number>(config?.idle_shutdown_minutes ?? 20);
  
  const [duration, setDuration] = useState<number>(config?.default_duration ?? 4.0);
  const [stgScale, setStgScale] = useState<number>(config?.default_stg ?? 0.8);
  const [modalityScale, setModalityScale] = useState<number>(config?.default_modality ?? 1.0);
  const [keyFilePath, setKeyFilePath] = useState(config?.key_file || '~/.ssh/pluto-gpu-key-2026-07-26.pem');

  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config) {
      if (config.region) setRegion(config.region);
      if (config.instance_type) setInstanceType(config.instance_type);
      if (config.idle_shutdown_minutes !== undefined) setIdleShutdown(config.idle_shutdown_minutes);
      if (config.default_duration !== undefined) setDuration(config.default_duration);
      if (config.default_stg !== undefined) setStgScale(config.default_stg);
      if (config.default_modality !== undefined) setModalityScale(config.default_modality);
      if (config.key_file) setKeyFilePath(config.key_file);
    }
  }, [config]);

  const handleSave = async () => {
    try {
      await updateConfigMutation.mutateAsync({
        region,
        instance_type: instanceType,
        idle_shutdown_minutes: idleShutdown,
        default_duration: duration,
        default_stg: stgScale,
        default_modality: modalityScale,
        key_file: keyFilePath,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      // ignore
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* 1. AWS Spot Fleet Settings */}
      <div className="bg-inset border border-line-200 rounded-[24px] p-7 flex flex-col justify-between gap-5 hover:border-line-400 transition-all">
        <div className="flex items-center justify-between pb-3 border-b border-line-200">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-ink-700" />
            <span className="font-mono text-xs font-bold text-ink uppercase tracking-wider">
              AWS Spot Fleet Settings
            </span>
          </div>
          <span className="font-mono text-[10.5px] text-verify bg-verify-soft px-2 py-0.5 rounded border border-verify">
            Fleet Config
          </span>
        </div>

        <div className="space-y-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-mono font-semibold uppercase text-ink-500">
              AWS Region
            </label>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="bg-raised border border-line-200 rounded-lg px-3 py-2 text-xs font-mono text-ink outline-none focus:border-line-400 transition-all cursor-pointer"
            >
              <option value="us-east-1">us-east-1 (N. Virginia · Lowest Latency)</option>
              <option value="us-east-2">us-east-2 (Ohio)</option>
              <option value="us-west-2">us-west-2 (Oregon)</option>
              <option value="eu-west-1">eu-west-1 (Ireland)</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-mono font-semibold uppercase text-ink-500">
              Instance Type &amp; Accelerator
            </label>
            <select
              value={instanceType}
              onChange={(e) => setInstanceType(e.target.value)}
              className="bg-raised border border-line-200 rounded-lg px-3 py-2 text-xs font-mono text-ink outline-none focus:border-line-400 transition-all cursor-pointer"
            >
              <option value="g6e.xlarge">g6e.xlarge — NVIDIA L40S 48GB · ~$0.75/hr (⭐ Recommended)</option>
              <option value="g5.xlarge">g5.xlarge — NVIDIA A10G 24GB · ~$0.51/hr</option>
              <option value="g6e.2xlarge">g6e.2xlarge — NVIDIA L40S 48GB (8 vCPU) · ~$1.10/hr</option>
              <option value="g6e.4xlarge">g6e.4xlarge — NVIDIA L40S 48GB (16 vCPU) · ~$1.60/hr</option>
              <option value="p4d.24xlarge">p4d.24xlarge — 8x A100 80GB SXM · ~$9.83/hr</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-mono font-semibold uppercase text-ink-500 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-ink-700" />
                Auto-Shutdown Watchdog
              </span>
              <span className="text-[10px] text-ink-700 font-normal lowercase">idle safety guard · auto-terminates</span>
            </label>
            <select
              value={idleShutdown}
              onChange={(e) => setIdleShutdown(Number(e.target.value))}
              className="bg-raised border border-line-200 rounded-lg px-3 py-2 text-xs font-mono text-ink outline-none focus:border-line-400 transition-all cursor-pointer"
            >
              <option value={10}>10 minutes</option>
              <option value={20}>20 minutes (Recommended Default)</option>
              <option value={30}>30 minutes</option>
              <option value={60}>60 minutes (1 Hour)</option>
              <option value={0}>Disabled (Continuous Spot Execution)</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={updateConfigMutation.isPending}
          className="font-sans text-xs font-semibold px-4 py-2 rounded-lg bg-accent text-accent-contrast hover:opacity-90 transition-all flex items-center justify-center gap-2 cursor-pointer mt-2 disabled:opacity-50"
        >
          {updateConfigMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
          <span>{saved ? 'Settings Saved ✓' : 'Save Fleet Settings'}</span>
        </button>
      </div>

      {/* 2. Generation & Guidance Defaults */}
      <div className="bg-inset border border-line-200 rounded-[24px] p-7 flex flex-col justify-between gap-5 hover:border-line-400 transition-all">
        <div className="flex items-center justify-between pb-3 border-b border-line-200">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-ink-700" />
            <span className="font-mono text-xs font-bold text-ink uppercase tracking-wider">
              Generation &amp; Guidance Defaults
            </span>
          </div>
          <span className="font-mono text-[10.5px] text-ink bg-strong px-2 py-0.5 rounded border border-line-400">
            Inference Defaults
          </span>
        </div>

        <div className="space-y-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-mono font-semibold uppercase text-ink-500">
              Default Duration (Seconds)
            </label>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="bg-raised border border-line-200 rounded-lg px-3 py-2 text-xs font-mono text-ink outline-none focus:border-line-400 transition-all cursor-pointer"
            >
              <option value={4.0}>4.0 Seconds (Standard Shot)</option>
              <option value={6.0}>6.0 Seconds (Cinematic Take)</option>
              <option value={8.0}>8.0 Seconds (Extended Sequence)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-mono font-semibold uppercase text-ink-500">
                STG Guidance Scale
              </label>
              <input
                type="number"
                min="0"
                max="5"
                step="0.1"
                value={stgScale}
                onChange={(e) => setStgScale(Number(e.target.value))}
                className="bg-raised border border-line-200 rounded-lg px-3 py-2 text-xs font-mono text-ink outline-none focus:border-line-400"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-mono font-semibold uppercase text-ink-500">
                Modality Scale
              </label>
              <input
                type="number"
                min="0"
                max="5"
                step="0.1"
                value={modalityScale}
                onChange={(e) => setModalityScale(Number(e.target.value))}
                className="bg-raised border border-line-200 rounded-lg px-3 py-2 text-xs font-mono text-ink outline-none focus:border-line-400"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-mono font-semibold uppercase text-ink-500 flex items-center gap-1.5">
              <Key className="w-3 h-3 text-ink-700" />
              SSH Key File Path
            </label>
            <input
              type="text"
              value={keyFilePath}
              onChange={(e) => setKeyFilePath(e.target.value)}
              placeholder="~/.ssh/pluto-gpu-key-2026-07-26.pem"
              className="bg-raised border border-line-200 rounded-lg px-3 py-2 text-xs font-mono text-ink outline-none focus:border-line-400"
            />
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={updateConfigMutation.isPending}
          className="font-sans text-xs font-semibold px-4 py-2 rounded-lg border border-line-300 bg-raised text-ink hover:bg-strong transition-all flex items-center justify-center gap-2 cursor-pointer mt-2 disabled:opacity-50"
        >
          {updateConfigMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
          <span>{saved ? 'Saved ✓' : 'Save Defaults'}</span>
        </button>
      </div>
    </div>
  );
}
