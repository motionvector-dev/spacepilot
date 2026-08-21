
import { Download, CheckCircle2, HardDrive, CloudSync } from 'lucide-react';

interface ModelWeight {
  id: string;
  category: string;
  name: string;
  precision: string;
  sizeGb: number;
  fit: 'Optimal' | 'Degraded' | 'OOM Warning';
  downloadProgress?: number;
  status: 'cached' | 'downloading' | 'remote';
}

const MODELS: ModelWeight[] = [
  {
    id: 'ltx-2.5-f8',
    category: 'Video Generation',
    name: 'LTX-2.5',
    precision: 'Float8',
    sizeGb: 12.4,
    fit: 'Optimal',
    status: 'cached',
  },
  {
    id: 'wan2.1',
    category: 'Video Generation',
    name: 'Wan2.1',
    precision: 'BF16',
    sizeGb: 32.1,
    fit: 'Degraded',
    status: 'downloading',
    downloadProgress: 45,
  },
  {
    id: 'kokoro-82m',
    category: 'Audio Generation',
    name: 'Kokoro-82M',
    precision: 'FP16',
    sizeGb: 0.16,
    fit: 'Optimal',
    status: 'remote',
  }
];

export function ModelWeightManager() {
  return (
    <div className="bg-[#18181b] border border-white/10 rounded-[24px] p-7 flex flex-col gap-5 hover:border-white/24 transition-all duration-150 ease-in-out">
      <div className="border-b border-white/10 pb-3.5 mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <HardDrive className="w-5 h-5 text-[#fafafa]" />
          <div>
            <h3 className="text-[17px] font-extrabold text-[#fafafa] leading-tight">Host Device Compute & Model Registry</h3>
            <p className="text-[12.5px] text-[#a1a1aa] mt-0.5">Zero-cloud local inference engine. Automatically probed hardware and curated model weights.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/30">
            Apple Metal (MPS)
          </span>
          <span className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/30">
            49.7 GB Usable
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
        <div className="bg-[#111114] border border-white/10 rounded-xl p-3">
          <div className="text-[10px] font-bold text-[#a1a1aa] uppercase font-mono">Device Architecture</div>
          <div className="text-[13.5px] font-bold text-[#fafafa] mt-1">Apple M3 Max</div>
        </div>
        <div className="bg-[#111114] border border-white/10 rounded-xl p-3">
          <div className="text-[10px] font-bold text-[#a1a1aa] uppercase font-mono">Total / Free Memory</div>
          <div className="text-[13.5px] font-bold text-[#fafafa] mt-1">64.0 GB / 40.2 GB Free</div>
        </div>
        <div className="bg-[#111114] border border-white/10 rounded-xl p-3">
          <div className="text-[10px] font-bold text-[#a1a1aa] uppercase font-mono">Instruction Set</div>
          <div className="text-[13.5px] font-bold text-[#10b981] mt-1">ARM_Neon_MPS</div>
        </div>
        <div className="bg-[#111114] border border-white/10 rounded-xl p-3">
          <div className="text-[10px] font-bold text-[#a1a1aa] uppercase font-mono">Local Cache Footprint</div>
          <div className="text-[13.5px] font-bold text-[#fafafa] mt-1">~/.cache/pluto/models/</div>
        </div>
      </div>

      <div>
        <div className="text-xs font-bold text-[#a1a1aa] uppercase font-mono mb-2 flex items-center justify-between">
          <span>Recommended Model Catalogue</span>
          <span className="flex items-center gap-1.5 text-[#a1a1aa]">
            <CloudSync className="w-3.5 h-3.5" />
            <span>R2 Cache Sync Active</span>
          </span>
        </div>
        <div className="overflow-x-auto border border-white/10 rounded-lg">
          <table className="w-full border-collapse text-left text-[12.5px]">
            <thead>
              <tr className="bg-[#111114] border-b border-white/10 font-mono text-[11px] text-[#a1a1aa]">
                <th className="p-3 font-medium">Task Category</th>
                <th className="p-3 font-medium">Model & Precision</th>
                <th className="p-3 font-medium">Disk Size</th>
                <th className="p-3 font-medium">Hardware Fit</th>
                <th className="p-3 font-medium text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {MODELS.map((model) => (
                <tr key={model.id} className="border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors">
                  <td className="p-3 text-[#a1a1aa]">{model.category}</td>
                  <td className="p-3">
                    <span className="font-bold text-[#fafafa]">{model.name}</span>
                    <span className="ml-2 font-mono text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-[#a1a1aa]">{model.precision}</span>
                  </td>
                  <td className="p-3 font-mono text-[#fafafa]">{model.sizeGb} GB</td>
                  <td className="p-3">
                    <span className={`font-mono text-[11px] px-2 py-0.5 rounded ${
                      model.fit === 'Optimal' ? 'bg-[#10b981]/10 text-[#10b981]' :
                      model.fit === 'Degraded' ? 'bg-[#f59e0b]/10 text-[#f59e0b]' :
                      'bg-[#f43535]/10 text-[#f43535]'
                    }`}>
                      {model.fit}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    {model.status === 'cached' && (
                      <span className="inline-flex items-center gap-1.5 text-[#10b981] font-medium text-xs">
                        <CheckCircle2 className="w-4 h-4" /> Ready
                      </span>
                    )}
                    {model.status === 'downloading' && (
                      <div className="flex flex-col items-end gap-1.5 w-full max-w-[120px] ml-auto">
                        <div className="flex items-center justify-between w-full text-xs font-medium text-[#3b82f6]">
                          <span>Downloading</span>
                          <span>{model.downloadProgress}%</span>
                        </div>
                        <div className="w-full h-1 bg-[#111114] rounded-full overflow-hidden">
                          <div className="h-full bg-[#3b82f6]" style={{ width: `${model.downloadProgress}%` }} />
                        </div>
                      </div>
                    )}
                    {model.status === 'remote' && (
                      <button className="inline-flex items-center gap-1.5 font-sans text-xs font-semibold px-2.5 py-1.5 rounded-md border border-white/14 bg-[#18181b] text-[#fafafa] hover:bg-[#222226] hover:border-white/24 transition-all cursor-pointer">
                        <Download className="w-3.5 h-3.5" /> Pull Cache
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
