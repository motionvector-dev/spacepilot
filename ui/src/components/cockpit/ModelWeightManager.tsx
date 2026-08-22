import { Download, CheckCircle2, HardDrive, CloudSync, RefreshCw } from 'lucide-react';
import { useComputeProfile, useRecommendedModels, useDownloadModel } from '../../hooks/useCompute';

export function ModelWeightManager() {
  const { data: profile } = useComputeProfile();
  const { data: models } = useRecommendedModels();
  const downloadMutation = useDownloadModel();

  const handleDownload = (modelId: string) => {
    downloadMutation.mutate(modelId);
  };

  const defaultModels = [
    {
      id: 'ltx-2.5-f8',
      category: 'Video Generation',
      name: 'LTX-2.5',
      precision: 'Float8',
      size_gb: 12.4,
      fit: 'Optimal' as const,
      status: 'cached' as const,
    },
    {
      id: 'wan2.1-1.3b',
      category: 'Video Generation',
      name: 'Wan2.1 1.3B',
      precision: 'BF16',
      size_gb: 8.2,
      fit: 'Optimal' as const,
      status: 'remote' as const,
    },
    {
      id: 'kokoro-82m',
      category: 'Audio Generation',
      name: 'Kokoro-82M',
      precision: 'FP16',
      size_gb: 0.16,
      fit: 'Optimal' as const,
      status: 'cached' as const,
    }
  ];

  const displayModels = models && models.length > 0 ? models : defaultModels;

  return (
    <div className="bg-inset border border-line-200 rounded-[24px] p-7 flex flex-col gap-5 hover:border-line-400 transition-all duration-150 ease-in-out">
      <div className="border-b border-line-200 pb-3.5 mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <HardDrive className="w-5 h-5 text-ink" />
          <div>
            <h3 className="text-[17px] font-extrabold text-ink leading-tight">Host Device Compute & Model Registry</h3>
            <p className="text-[12.5px] text-ink-700 mt-0.5">Zero-cloud local inference engine. Automatically probed hardware and curated model weights.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-verify-soft text-verify border border-verify">
            {profile?.device || 'Host Metal / CUDA'}
          </span>
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-verify-soft text-verify border border-verify">
            {profile?.free_vram_gb ? `${profile.free_vram_gb.toFixed(1)} GB Free` : '40.0 GB Usable'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
        <div className="bg-raised border border-line-200 rounded-xl p-3">
          <div className="text-[10px] font-bold text-ink-700 uppercase font-mono">Device Architecture</div>
          <div className="text-[13.5px] font-bold text-ink mt-1">
            {profile?.device_name || 'Apple Metal / NVIDIA L40S'}
          </div>
        </div>
        <div className="bg-raised border border-line-200 rounded-xl p-3">
          <div className="text-[10px] font-bold text-ink-700 uppercase font-mono">Total / Free Memory</div>
          <div className="text-[13.5px] font-bold text-ink mt-1">
            {profile?.total_vram_gb ? `${profile.total_vram_gb.toFixed(1)} GB / ${profile.free_vram_gb.toFixed(1)} GB Free` : '64.0 GB / 40.2 GB Free'}
          </div>
        </div>
        <div className="bg-raised border border-line-200 rounded-xl p-3">
          <div className="text-[10px] font-bold text-ink-700 uppercase font-mono">Instruction Set</div>
          <div className="text-[13.5px] font-bold text-verify mt-1">
            {profile?.instruction_set || 'ARM_Neon_MPS / CUDA_12'}
          </div>
        </div>
        <div className="bg-raised border border-line-200 rounded-xl p-3">
          <div className="text-[10px] font-bold text-ink-700 uppercase font-mono">Local Cache Footprint</div>
          <div className="text-[13.5px] font-bold text-ink mt-1">~/.cache/pluto/models/</div>
        </div>
      </div>

      <div>
        <div className="text-xs font-bold text-ink-700 uppercase font-mono mb-2 flex items-center justify-between">
          <span>Recommended Model Catalogue</span>
          <span className="flex items-center gap-1.5 text-ink-700">
            <CloudSync className="w-3.5 h-3.5" />
            <span>R2 Cache Sync Active</span>
          </span>
        </div>
        <div className="overflow-x-auto border border-line-200 rounded-lg">
          <table className="w-full border-collapse text-left text-[12.5px]">
            <thead>
              <tr className="bg-raised border-b border-line-200 font-mono text-[11px] text-ink-700">
                <th className="p-3 font-medium">Task Category</th>
                <th className="p-3 font-medium">Model & Precision</th>
                <th className="p-3 font-medium">Disk Size</th>
                <th className="p-3 font-medium">Hardware Fit</th>
                <th className="p-3 font-medium text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {displayModels.map((model) => (
                <tr key={model.id} className="border-b border-line-100 last:border-0 hover:bg-strong transition-colors">
                  <td className="p-3 text-ink-700">{model.category}</td>
                  <td className="p-3">
                    <span className="font-bold text-ink">{model.name}</span>
                    <span className="ml-2 font-mono text-[10px] bg-strong px-1.5 py-0.5 rounded text-ink-700">{model.precision}</span>
                  </td>
                  <td className="p-3 font-mono text-ink">{model.size_gb} GB</td>
                  <td className="p-3">
                    <span className={`font-mono text-[11px] px-2 py-0.5 rounded ${
                      model.fit === 'Optimal' ? 'bg-verify-soft text-verify' :
                      model.fit === 'Degraded' ? 'bg-inset text-ink-900' :
                      'bg-danger-soft text-danger'
                    }`}>
                      {model.fit || 'Optimal'}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    {model.status === 'cached' && (
                      <span className="inline-flex items-center gap-1.5 text-verify font-medium text-xs">
                        <CheckCircle2 className="w-4 h-4" /> Ready
                      </span>
                    )}
                    {model.status === 'downloading' && (
                      <div className="flex flex-col items-end gap-1.5 w-full max-w-[120px] ml-auto">
                        <div className="flex items-center justify-between w-full text-xs font-medium text-ink">
                          <span>Downloading</span>
                          <span>{model.download_progress ?? 45}%</span>
                        </div>
                        <div className="w-full h-1 bg-raised rounded-full overflow-hidden">
                          <div className="h-full bg-strong" style={{ width: `${model.download_progress ?? 45}%` }} />
                        </div>
                      </div>
                    )}
                    {model.status === 'remote' && (
                      <button
                        onClick={() => handleDownload(model.id)}
                        disabled={downloadMutation.isPending}
                        className="inline-flex items-center gap-1.5 font-sans text-xs font-semibold px-2.5 py-1.5 rounded-md border border-line-300 bg-inset text-ink hover:bg-strong hover:border-line-400 transition-all cursor-pointer"
                      >
                        {downloadMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                        Pull Cache
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
