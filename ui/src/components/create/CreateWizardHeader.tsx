import { useGpuStatus } from '../../hooks/useGpuStatus';

export function CreateWizardHeader() {
  const { data: statusData, isError } = useGpuStatus();

  let gpuText = 'Checking GPU...';
  let dotColor = 'bg-ink-500';

  if (isError) {
    gpuText = 'Local Mode';
    dotColor = 'bg-ink-300';
  } else if (statusData?.gpu_online) {
    const vramInfo = statusData.vram_used_gb ? `${statusData.vram_used_gb.toFixed(1)}G` : 'L40S 48GB';
    gpuText = `GPU Online · ${vramInfo}`;
    dotColor = 'bg-verify';
  } else if (statusData) {
    gpuText = 'GPU Standby';
    dotColor = 'bg-ink-500';
  }

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-6 h-14 bg-surface/90 backdrop-blur-md border-b border-line-200">
      <div className="flex items-center gap-6">
        {/* Brand Group */}
        <a href="/" className="flex items-center gap-2.5 text-ink hover:opacity-90 transition-opacity">
          <svg className="h-5 w-auto" viewBox="0 0 52 46" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g className="fill-ink-700">
              <rect x="0" y="0" width="4.11" height="44" />
              <rect x="4.73" y="0" width="4.11" height="44" />
              <rect x="9.45" y="0" width="4.11" height="44" />
              <rect x="37.82" y="0" width="4.11" height="44" />
              <rect x="42.55" y="0" width="4.11" height="44" />
              <rect x="47.27" y="0" width="4.11" height="44" />
            </g>
            <g className="fill-ink">
              <rect x="14.18" y="7.84" width="4.11" height="22.21" />
              <rect x="18.91" y="16.7" width="4.11" height="23.98" />
              <rect x="23.64" y="25.57" width="4.11" height="20.43" />
              <rect x="28.36" y="16.7" width="4.11" height="23.98" />
              <rect x="33.09" y="7.84" width="4.11" height="22.21" />
            </g>
          </svg>
          <span className="font-bold text-sm tracking-wider text-ink">
            SPACEPILOT <span className="text-ink-500 font-medium">STUDIO</span>
          </span>
        </a>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-5 text-[13px]">
          <a href="/" className="text-ink-500 hover:text-ink transition-colors font-medium">Home</a>
          <a href="/create" className="text-ink font-semibold transition-colors">Create</a>
          <a href="/studio" className="text-ink-500 hover:text-ink transition-colors font-medium">Editor</a>
          <a href="/oven.html" className="text-ink-500 hover:text-ink transition-colors font-medium">Oven</a>
          <a href="/cockpit" className="text-ink-500 hover:text-ink transition-colors font-medium">Cockpit</a>
          <a href="/docs" className="text-ink-500 hover:text-ink transition-colors font-medium">Docs</a>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {/* GPU Telemetry Pill */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-raised border border-line-200 font-mono text-[12px] text-ink-700">
          <div className={`w-2 h-2 rounded-full ${dotColor} animate-pulse`} />
          <span>{gpuText}</span>
        </div>

        {/* Header Action Shortcuts */}
        <a
          href="/cockpit"
          className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-inset hover:bg-strong border border-line-200 text-xs font-semibold text-ink-900 hover:text-ink transition-all cursor-pointer"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
          <span>Cockpit</span>
        </a>

        <a
          href="/studio"
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-inset hover:bg-strong border border-line-200 hover:border-line-400 text-xs font-semibold text-ink hover:text-ink transition-all cursor-pointer"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <span>Pro Editor</span>
        </a>
      </div>
    </header>
  );
}
