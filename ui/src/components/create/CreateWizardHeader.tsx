import { useGpuStatus } from '../../hooks/useGpuStatus';

export function CreateWizardHeader() {
  const { data: statusData, isError } = useGpuStatus();

  let gpuText = 'Checking GPU...';
  let dotColor = 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]';

  if (isError) {
    gpuText = 'Local Mode';
    dotColor = 'bg-zinc-500 shadow-none';
  } else if (statusData?.gpu_online) {
    const vramInfo = statusData.vram_used_gb ? `${statusData.vram_used_gb.toFixed(1)}G` : 'L40S 48GB';
    gpuText = `GPU Online · ${vramInfo}`;
    dotColor = 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]';
  } else if (statusData) {
    gpuText = 'GPU Standby';
    dotColor = 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]';
  }

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-6 h-14 bg-[#09090b]/90 backdrop-blur-md border-b border-white/[0.08]">
      <div className="flex items-center gap-6">
        {/* Brand Group */}
        <a href="/" className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
          <svg className="h-5 w-auto" viewBox="0 0 52 46" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g fill="#a1a1aa">
              <rect x="0" y="0" width="4.11" height="44" />
              <rect x="4.73" y="0" width="4.11" height="44" />
              <rect x="9.45" y="0" width="4.11" height="44" />
              <rect x="37.82" y="0" width="4.11" height="44" />
              <rect x="42.55" y="0" width="4.11" height="44" />
              <rect x="47.27" y="0" width="4.11" height="44" />
            </g>
            <g fill="#fafafa">
              <rect x="14.18" y="7.84" width="4.11" height="22.21" />
              <rect x="18.91" y="16.7" width="4.11" height="23.98" />
              <rect x="23.64" y="25.57" width="4.11" height="20.43" />
              <rect x="28.36" y="16.7" width="4.11" height="23.98" />
              <rect x="33.09" y="7.84" width="4.11" height="22.21" />
            </g>
          </svg>
          <span className="font-bold text-sm tracking-wider text-white">
            SPACEPILOT <span className="text-white/40 font-medium">STUDIO</span>
          </span>
        </a>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-5 text-[13px]">
          <a href="/" className="text-white/50 hover:text-white transition-colors font-medium">Home</a>
          <a href="/create" className="text-white font-semibold transition-colors">Create</a>
          <a href="/studio" className="text-white/50 hover:text-white transition-colors font-medium">Editor</a>
          <a href="/oven.html" className="text-white/50 hover:text-white transition-colors font-medium">Oven</a>
          <a href="/cockpit" className="text-white/50 hover:text-white transition-colors font-medium">Cockpit</a>
          <a href="/docs" className="text-white/50 hover:text-white transition-colors font-medium">Docs</a>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {/* GPU Telemetry Pill */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#111114] border border-white/[0.08] font-mono text-[12px] text-white/70">
          <div className={`w-2 h-2 rounded-full ${dotColor} animate-pulse`} />
          <span>{gpuText}</span>
        </div>

        {/* Header Action Shortcuts */}
        <a 
          href="/cockpit"
          className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#18181b] hover:bg-[#222226] border border-white/[0.08] text-xs font-semibold text-white/80 hover:text-white transition-all cursor-pointer"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
          <span>Cockpit</span>
        </a>

        <a 
          href="/studio"
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-[#18181b] hover:bg-[#222226] border border-white/[0.08] text-xs font-semibold text-white/90 hover:text-white hover:border-white/20 transition-all cursor-pointer shadow-sm"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <span>Pro Editor</span>
        </a>
      </div>
    </header>
  );
}
