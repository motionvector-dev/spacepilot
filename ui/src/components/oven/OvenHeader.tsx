
export function OvenHeader() {
  return (
    <header className="h-16 bg-surface border-b border-line-200 flex items-center justify-between px-6 shrink-0 z-10">
      <div className="flex items-center gap-3">
        <a href="/" className="flex items-center gap-2.5 no-underline text-ink">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4.5 3.5L19.5 12L4.5 20.5V3.5Z" fill="var(--mark-ink)" stroke="var(--mark-recessive)" strokeWidth="1.2"/>
          </svg>
          <span className="text-base font-extrabold tracking-tight">SpacePilot</span>
          <span className="font-mono text-[11px] font-bold text-verify bg-verify-soft border border-verify/30 px-2 py-0.5 rounded uppercase">
            Oven · ADLC Swarm
          </span>
        </a>
      </div>

      <nav className="flex items-center gap-5">
        <a href="/" className="text-[13px] font-medium text-ink-700 no-underline hover:text-ink-900 transition-colors">Home</a>
        <a href="/create" className="text-[13px] font-medium text-ink-700 no-underline hover:text-ink-900 transition-colors">Create</a>
        <a href="/studio" className="text-[13px] font-medium text-ink-700 no-underline hover:text-ink-900 transition-colors">Editor</a>
        <a href="/oven.html" className="text-[13px] font-semibold text-ink no-underline">Oven</a>
        <a href="/cockpit" className="text-[13px] font-medium text-ink-700 no-underline hover:text-ink-900 transition-colors">Cockpit</a>
        <a href="/docs" className="text-[13px] font-medium text-ink-700 no-underline hover:text-ink-900 transition-colors">Docs</a>
      </nav>

      <div className="flex items-center gap-3">
        <div className="flex items-center bg-inset border border-line-200 rounded-full p-0.5 gap-0.5">
          <button title="Light Mode" className="text-ink-700 hover:text-ink-900 p-1 rounded-full flex items-center justify-center transition-all bg-transparent border-none cursor-pointer">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
          </button>
          <button title="Dark Mode" className="text-ink-900 bg-strong p-1 rounded-full flex items-center justify-center transition-all border-none cursor-pointer">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
          </button>
          <button title="System Match" className="text-ink-700 hover:text-ink-900 p-1 rounded-full flex items-center justify-center transition-all bg-transparent border-none cursor-pointer">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
          </button>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs bg-inset border border-line-200 px-3 py-1.5 rounded-md">
          <span className="w-2 h-2 rounded-full bg-verify"></span>
          <span>Swarms: <strong className="font-bold">3 Active</strong></span>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs bg-inset border border-line-200 px-3 py-1.5 rounded-md">
          <span className="w-2 h-2 rounded-full bg-verify"></span>
          <span>Tests: <strong className="font-bold">142/142 (100%)</strong></span>
        </div>
      </div>
    </header>
  );
}
