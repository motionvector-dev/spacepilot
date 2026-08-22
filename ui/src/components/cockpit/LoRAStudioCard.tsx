import { useState } from 'react';
import { Settings2, Layers, RefreshCw, Power } from 'lucide-react';

interface LoraAdapter {
  id: string;
  name: string;
  baseModel: string;
  rank: number;
  status: 'active' | 'inactive' | 'training';
  progress?: number;
}

const ADAPTERS: LoraAdapter[] = [
  { id: 'lora-1', name: 'Cinematic_Lighting_v2', baseModel: 'LTX-2.5', rank: 128, status: 'active' },
  { id: 'lora-2', name: 'Anime_Style_XL', baseModel: 'LTX-2.5', rank: 64, status: 'inactive' },
  { id: 'lora-3', name: 'Product_Macro_Shots', baseModel: 'Wan2.1', rank: 256, status: 'training', progress: 68 },
];

export function LoRAStudioCard() {
  const [activeAdapter, setActiveAdapter] = useState<string>('lora-1');

  return (
    <div className="bg-inset border border-line-200 rounded-[24px] p-7 flex flex-col gap-5 hover:border-line-400 transition-all duration-150 ease-in-out">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[18px] font-bold text-ink flex items-center gap-2">
            <Layers className="w-5 h-5 text-ink-700" />
            PEFT LoRA Studio
          </h3>
          <p className="text-[13px] text-ink-700 mt-1">
            1-Click fine-tuning & active adapter hot-swapping.
          </p>
        </div>
        <button className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-transparent bg-accent text-accent-contrast hover:brightness-110 transition-all cursor-pointer flex items-center gap-2">
          <Settings2 className="w-4 h-4" />
          New Fine-Tune
        </button>
      </div>

      <div className="flex flex-col gap-3 mt-2">
        <div className="text-[11px] font-bold text-ink-500 uppercase font-mono tracking-wider">
          Adapter Registry
        </div>

        <div className="flex flex-col gap-2.5">
          {ADAPTERS.map((adapter) => (
            <div
              key={adapter.id}
              className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                adapter.id === activeAdapter
                  ? 'bg-strong border-line-400'
                  : 'bg-raised border-line-200 hover:border-line-400'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  adapter.status === 'active' ? 'bg-verify' :
                  adapter.status === 'training' ? 'bg-strong animate-pulse' :
                  'bg-strong'
                }`} />
                <div>
                  <div className="text-sm font-semibold text-ink">{adapter.name}</div>
                  <div className="text-[11px] font-mono text-ink-700 mt-0.5">
                    {adapter.baseModel} · Rank {adapter.rank}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {adapter.status === 'training' ? (
                  <div className="flex items-center gap-3 w-32">
                    <span className="text-[11px] font-mono text-ink-700">Training · {adapter.progress}%</span>
                    <div className="flex-1 h-1.5 bg-inset rounded-full overflow-hidden">
                      <div className="h-full bg-strong" style={{ width: `${adapter.progress}%` }} />
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setActiveAdapter(adapter.id)}
                    disabled={adapter.id === activeAdapter}
                    className={`font-sans text-[11px] font-semibold px-3 py-1.5 rounded-md border transition-all flex items-center gap-1.5 cursor-pointer ${
                      adapter.id === activeAdapter
                        ? 'bg-strong text-ink-900 border-line-400'
                        : 'bg-inset text-ink border-line-300 hover:bg-strong hover:border-line-400'
                    }`}
                  >
                    {adapter.id === activeAdapter ? (
                      <>
                        <Power className="w-3.5 h-3.5" />
                        Active
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-3.5 h-3.5" />
                        Hot-Swap
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
