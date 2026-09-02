import { 
  GitBranch, 
  ExternalLink
} from 'lucide-react';

export default function BlueprintPage() {
  const milestones = [
    { wave: 'Wave 1', name: 'Foundation & Core Runtime', status: 'Shipped', tests: '139 Tests Green', date: '2026-08-20' },
    { wave: 'Wave 2', name: 'In-Process Kokoro Audio & Ducking', status: 'Shipped', tests: '142 Tests Green', date: '2026-08-21' },
    { wave: 'Wave 3', name: 'FastMCP Directing Protocol', status: 'Shipped', tests: 'Verified', date: '2026-08-21' },
    { wave: 'Wave 4', name: 'React 19 + Vite 6 UI Modularization', status: 'Shipped', tests: 'Passing', date: '2026-08-21' },
    { wave: 'Wave 5', name: 'FastAPI Backend Package (src/pluto)', status: 'Cooking', tests: 'pluto-backend', date: 'Active' },
  ];

  return (
    <div className="min-h-screen bg-ground text-ink flex flex-col font-sans">
      {/* Header */}
      <header className="h-14 bg-surface border-b border-line-200 px-6 flex items-center justify-between z-20">
        <div className="flex items-center gap-4">
          <a href="/" className="flex items-center gap-2 text-sm font-extrabold tracking-tight">
            <span>🛸</span>
            <span>SpacePilot Blueprint</span>
          </a>
          <div className="h-4 w-px bg-line-300" />
          <span className="font-mono text-xs text-ink-700 bg-inset px-2 py-0.5 rounded border border-line-400">
            Strategic Master Plan
          </span>
        </div>

        <div className="flex items-center gap-4 font-mono text-xs text-ink-900">
          <a href="/admin/oven" className="text-ink-900 hover:underline flex items-center gap-1">
            Oven Kanban <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </header>

      {/* Main Roadmap */}
      <main className="flex-1 max-w-5xl mx-auto w-full p-8 flex flex-col gap-8">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-ink mb-2">
            Strategic Architecture & Milestone Roadmap
          </h1>
          <p className="text-sm text-ink-900">
            High-level tracking for SpacePilot generative cinema workstation. Live task execution is orchestrated in the internal Oven board.
          </p>
        </div>

        {/* Milestone Table */}
        <div className="bg-surface border border-line-200 rounded-xl overflow-hidden">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-raised border-b border-line-200 text-ink-500 uppercase text-[10px]">
              <tr>
                <th className="p-3.5 pl-5">Wave / Phase</th>
                <th className="p-3.5">Capability / Target</th>
                <th className="p-3.5">Test Suite SLA</th>
                <th className="p-3.5 pr-5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-100 text-ink-900">
              {milestones.map((m, idx) => (
                <tr key={idx} className="hover:bg-raised">
                  <td className="p-3.5 pl-5 font-bold text-ink flex items-center gap-2">
                    <GitBranch className="w-3 h-3 text-ink-500" />
                    {m.wave}
                  </td>
                  <td className="p-3.5 font-sans font-medium text-ink">{m.name}</td>
                  <td className="p-3.5 text-verify">{m.tests}</td>
                  <td className="p-3.5 pr-5">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      m.status === 'Shipped'
                        ? 'bg-verify-soft text-verify border border-verify/30'
                        : 'bg-inset text-ink border border-line-400'
                    }`}>
                      {m.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
