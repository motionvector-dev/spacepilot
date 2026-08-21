import { useEngines } from '../../hooks/useCompute';

interface ModelEngineStepProps {
  selected: string;
  setSelected: (id: string) => void;
}

export function ModelEngineStep({ selected, setSelected }: ModelEngineStepProps) {
  const { data: enginesData } = useEngines();

  const fallbackEngines = [
    { id: 'wan-14b', name: 'Wan2.1 14B', vram: '18GB', time: '~45s', color: 'emerald' },
    { id: 'wan-1.3b', name: 'Wan2.1 1.3B', vram: '8GB', time: '~12s', color: 'cyan' },
    { id: 'hunyuan', name: 'HunyuanVideo', vram: '16GB', time: '~35s', color: 'amber' },
    { id: 'ltx-2.5', name: 'LTX-2.5', vram: '10GB', time: '~18s', color: 'purple' },
  ];

  const engines = enginesData && enginesData.length > 0 
    ? enginesData.map((e, idx) => ({
        id: e.id,
        name: e.name,
        vram: `${e.vram_requirement_gb}GB`,
        time: `~${e.cold_start_seconds}s`,
        color: ['purple', 'emerald', 'cyan', 'amber'][idx % 4],
      }))
    : fallbackEngines;

  const colorMap: Record<string, string> = {
    emerald: 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]',
    cyan: 'bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.6)]',
    amber: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]',
    purple: 'bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]',
  };

  return (
    <div className="flex flex-col gap-4 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm">
      <div className="flex justify-between items-center">
        <h2 className="text-[13px] font-semibold text-white/60 uppercase tracking-wider">Engine Recipe</h2>
        <span className="text-[12px] font-mono text-white/50">DiT Multi-Engine</span>
      </div>
      
      <div className="grid grid-cols-1 gap-3">
        {engines.map(eng => {
          const isSelected = selected === eng.id;
          return (
            <button
              key={eng.id}
              onClick={() => setSelected(eng.id)}
              className={`flex flex-col gap-2.5 p-3.5 rounded-lg border text-left transition-all cursor-pointer ${
                isSelected 
                  ? 'bg-[#18181b] border-white/20 shadow-sm' 
                  : 'bg-black border-white/[0.08] hover:bg-[#111114] hover:border-white/[0.14]'
              }`}
            >
              <div className="flex justify-between items-center w-full">
                <span className="font-semibold text-[14px] text-white">{eng.name}</span>
                {isSelected && (
                  <div className={`w-2 h-2 rounded-full ${colorMap[eng.color] || colorMap.purple}`} />
                )}
              </div>
              <div className="flex gap-2 text-[11px] font-mono text-white/50">
                <span className="px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08]">VRAM: {eng.vram}</span>
                <span className="px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08]">Cold: {eng.time}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
