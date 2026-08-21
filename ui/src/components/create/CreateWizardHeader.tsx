import { useGpuStatus } from '../../hooks/useGpuStatus';

export function CreateWizardHeader() {
  const { data: statusData, isError } = useGpuStatus();

  let gpuText = 'Checking GPU...';
  let dotColor = 'bg-amber-500';

  if (isError) {
    gpuText = 'GPU Offline';
    dotColor = 'bg-rose-500';
  } else if (statusData?.gpu_online) {
    gpuText = 'GPU Online · L40S 48GB';
    dotColor = 'bg-emerald-500';
  } else if (statusData) {
    gpuText = 'GPU Standby';
    dotColor = 'bg-amber-500';
  }

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-6 h-14 bg-[#09090b]/80 backdrop-blur-md border-b border-white/[0.08]">
      <div className="flex items-center gap-4">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-[13px] text-white/50">
          <a href="/" className="hover:text-white transition-colors font-medium">Spacepilot</a>
          <span className="text-white/30 text-[11px]">/</span>
          <span className="text-white font-semibold">Create Video</span>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {/* GPU Telemetry Pill */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#111114] border border-white/[0.08] font-mono text-[12px] text-white/70">
          <div className={`w-2 h-2 rounded-full ${dotColor} shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse`} />
          {gpuText}
        </div>
        <a 
          href="/studio"
          className="px-3.5 py-1.5 rounded-md bg-[#18181b] hover:bg-[#222226] border border-white/[0.08] text-xs font-semibold transition-colors flex items-center gap-2 text-white/80 hover:text-white cursor-pointer"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          Pro Editor
        </a>
      </div>
    </header>
  );
}
