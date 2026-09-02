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
    <div className="bg-[#18181b] border border-white/10 rounded-[24px] p-7 flex flex-col gap-5 hover:border-white/24 transition-all duration-150 ease-in-out">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[18px] font-bold text-[#fafafa] flex items-center gap-2">
            <Layers className="w-5 h-5 text-[#a855f7]" />
            PEFT LoRA Studio
          </h3>
          <p className="text-[13px] text-[#a1a1aa] mt-1">
            1-Click fine-tuning & active adapter hot-swapping.
          </p>
        </div>
        <button className="font-sans text-[13px] font-semibold px-4 py-2 rounded-md border border-transparent bg-[#fafafa] text-[#09090b] hover:bg-white transition-all shadow-sm cursor-pointer flex items-center gap-2">
          <Settings2 className="w-4 h-4" />
          New Fine-Tune
        </button>
      </div>

      <div className="flex flex-col gap-3 mt-2">
        <div className="text-[11px] font-bold text-[#71717a] uppercase font-mono tracking-wider">
          Adapter Registry
        </div>
        
        <div className="flex flex-col gap-2.5">
          {ADAPTERS.map((adapter) => (
            <div 
              key={adapter.id} 
              className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                adapter.id === activeAdapter 
                  ? 'bg-[#a855f7]/10 border-[#a855f7]/30' 
                  : 'bg-[#111114] border-white/10 hover:border-white/20'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  adapter.status === 'active' ? 'bg-[#10b981] shadow-[0_0_6px_#10b981]' : 
                  adapter.status === 'training' ? 'bg-[#f59e0b] animate-pulse' : 
                  'bg-[#71717a]'
                }`} />
                <div>
                  <div className="text-sm font-semibold text-[#fafafa]">{adapter.name}</div>
                  <div className="text-[11px] font-mono text-[#a1a1aa] mt-0.5">
                    {adapter.baseModel} · Rank {adapter.rank}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {adapter.status === 'training' ? (
                  <div className="flex items-center gap-3 w-32">
                    <span className="text-[11px] font-mono text-[#f59e0b]">{adapter.progress}%</span>
                    <div className="flex-1 h-1.5 bg-[#18181b] rounded-full overflow-hidden">
                      <div className="h-full bg-[#f59e0b]" style={{ width: `${adapter.progress}%` }} />
                    </div>
                  </div>
                ) : (
                  <button 
                    onClick={() => setActiveAdapter(adapter.id)}
                    disabled={adapter.id === activeAdapter}
                    className={`font-sans text-[11px] font-semibold px-3 py-1.5 rounded-md border transition-all flex items-center gap-1.5 cursor-pointer ${
                      adapter.id === activeAdapter 
                        ? 'bg-[#a855f7]/20 text-[#a855f7] border-[#a855f7]/30'
                        : 'bg-[#18181b] text-[#fafafa] border-white/14 hover:bg-[#222226] hover:border-white/24'
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
