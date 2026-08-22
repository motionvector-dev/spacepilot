
export function DocsSidebar() {
  return (
    <aside className="w-[280px] bg-surface border-r border-line-300 h-screen fixed overflow-y-auto px-6 py-8 flex flex-col gap-6 z-[100] md:translate-x-0 -translate-x-full transition-transform">
      <div className="text-xl font-bold tracking-tight flex items-center gap-2">
        <svg viewBox="0 0 24 24" className="w-6 h-6 fill-none stroke-current stroke-2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
        SpacePilot Docs
      </div>

      <div className="relative">
        <svg className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-500 fill-none stroke-current stroke-2" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" strokeLinecap="round"/></svg>
        <input type="text" className="w-full py-2 pr-3 pl-8 bg-ground border border-line-300 rounded-md text-ink text-sm focus:outline-none focus:border-line-500 placeholder-ink-500" placeholder="Search documentation..." />
      </div>

      <nav className="flex flex-col gap-6 flex-1">
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-500 font-semibold mb-2">Getting Started</div>
          <ul className="list-none flex flex-col gap-1">
            <li><a href="#quickstart" className="text-ink bg-inset block px-2 py-1.5 rounded text-sm no-underline">Quickstart</a></li>
            <li><a href="#architecture" className="text-ink-700 hover:text-ink hover:bg-inset block px-2 py-1.5 rounded text-sm no-underline transition-colors">Platform Architecture</a></li>
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-500 font-semibold mb-2">Core Engine</div>
          <ul className="list-none flex flex-col gap-1">
            <li><a href="#models" className="text-ink-700 hover:text-ink hover:bg-inset block px-2 py-1.5 rounded text-sm no-underline transition-colors">Model Zoo & DiT Engines</a></li>
            <li><a href="#audio" className="text-ink-700 hover:text-ink hover:bg-inset block px-2 py-1.5 rounded text-sm no-underline transition-colors">Audio Sidechain</a></li>
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-500 font-semibold mb-2">Integration</div>
          <ul className="list-none flex flex-col gap-1">
            <li><a href="#fastmcp" className="text-ink-700 hover:text-ink hover:bg-inset block px-2 py-1.5 rounded text-sm no-underline transition-colors">Agentic FastMCP</a></li>
            <li><a href="#rest-api" className="text-ink-700 hover:text-ink hover:bg-inset block px-2 py-1.5 rounded text-sm no-underline transition-colors">REST API & Auth</a></li>
            <li><a href="#economics" className="text-ink-700 hover:text-ink hover:bg-inset block px-2 py-1.5 rounded text-sm no-underline transition-colors">SkyPilot Economics</a></li>
          </ul>
        </div>
      </nav>

      <div className="flex bg-inset rounded-md p-0.5 mt-auto">
        <button className="flex-1 bg-transparent border-none text-ink-700 p-1 rounded text-xs cursor-pointer">Light</button>
        <button className="flex-1 bg-ground text-ink shadow-sm border-none p-1 rounded text-xs cursor-pointer">Dark</button>
        <button className="flex-1 bg-transparent border-none text-ink-700 p-1 rounded text-xs cursor-pointer">System</button>
      </div>
    </aside>
  );
}
