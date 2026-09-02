import { KanbanCard } from './KanbanCard';

export function KanbanMatrix() {
  return (
    <main className="flex-1 grid grid-cols-5 gap-4 p-4 lg:p-5 overflow-x-auto overflow-y-hidden bg-[radial-gradient(circle_at_50%_0%,rgba(16,185,129,0.03)_0%,transparent_70%)] min-w-[1200px]">
      {/* Column 1: Backburner */}
      <section className="bg-[#12141d]/85 border border-white/10 rounded-xl flex flex-col h-full overflow-hidden backdrop-blur-md">
        <div className="p-3.5 px-4 border-b border-white/10 flex items-center justify-between shrink-0">
          <div className="font-mono text-xs font-extrabold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            Backburner
          </div>
          <span className="font-mono text-[11px] font-bold bg-white/10 px-2 py-0.5 rounded-full text-slate-400">3</span>
        </div>
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-3">
          <KanbanCard priority="p2" badgeText="P2 · Horizon 4" title="4D Gaussian Splatting" description="Volumetric light fields & spatial video rendering for Apple Vision Pro / Meta Quest 3." persona="Research" status="Est: Wave 6" />
          <KanbanCard priority="p2" badgeText="P2 · Horizon 5" title="60 FPS StreamDiffusion" description="Sub-50ms WebRTC interactive latent streaming with real-time 3D camera joystick." persona="Realtime" status="Est: Wave 6" />
          <KanbanCard priority="p2" badgeText="P2 · Horizon 5" title="Bio & Protein Surrogates" description="AlphaFold / ESMFold ONNX CUDA execution pipelines on spot GPU hardware." persona="Science" status="Est: Wave 6" />
        </div>
      </section>

      {/* Column 2: Planned */}
      <section className="bg-[#12141d]/85 border border-white/10 rounded-xl flex flex-col h-full overflow-hidden backdrop-blur-md">
        <div className="p-3.5 px-4 border-b border-white/10 flex items-center justify-between shrink-0">
          <div className="font-mono text-xs font-extrabold uppercase tracking-wider text-purple-500 flex items-center gap-1.5">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
            Planned
          </div>
          <span className="font-mono text-[11px] font-bold bg-white/10 px-2 py-0.5 rounded-full text-slate-400">3</span>
        </div>
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-3">
          <KanbanCard priority="p1" badgeText="P1 · Wave 4/5" title="1-Click LoRA Studio" description="Upload 10-20 reference images directly in Cockpit, run spot PEFT training ($0.40), hot-swap adapter." persona="LoRA Agent" status="Est: 2h" />
          <KanbanCard priority="p1" badgeText="P1 · Wave 4/5" title="Spot Training & R2 Sync" description="Multi-node training recipes with preemption recovery and loss curve telemetry streaming." persona="MLOps" status="Est: 3h" />
          <KanbanCard priority="p1" badgeText="P1 · Wave 4/5" title="Top Model Leaderboard Recipes" description="1-click hardware allocation recipes for Wan2.1, HunyuanVideo, DeepSeek-R1, and Qwen2.5-VL." persona="Catalog" status="Est: 1.5h" />
        </div>
      </section>

      {/* Column 3: In-Flight */}
      <section className="bg-[#12141d]/85 border border-white/10 rounded-xl flex flex-col h-full overflow-hidden backdrop-blur-md">
        <div className="p-3.5 px-4 border-b border-white/10 flex items-center justify-between shrink-0">
          <div className="font-mono text-xs font-extrabold uppercase tracking-wider text-amber-500 flex items-center gap-1.5">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"></circle><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path></svg>
            In-Flight
          </div>
          <span className="font-mono text-[11px] font-bold bg-white/10 px-2 py-0.5 rounded-full text-slate-400">2</span>
        </div>
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-3">
          <KanbanCard priority="p1" badgeText="P1 · Wave 5" title="1-Click LoRA Studio" description="Upload 10-20 reference images in Cockpit, run spot PEFT training ($0.40), hot-swap adapter." persona="LoRA Agent" status="In Progress" statusColor="#f59e0b" borderColor="rgba(245, 158, 11, 0.4)" />
          <KanbanCard priority="p1" badgeText="P1 · Wave 5" title="Spot Training & R2 Checkpoints" description="Multi-node training recipes with preemption recovery and loss curve telemetry streaming." persona="MLOps" status="In Progress" statusColor="#f59e0b" borderColor="rgba(245, 158, 11, 0.4)" />
        </div>
      </section>

      {/* Column 4: Review Gate */}
      <section className="bg-[#12141d]/85 border border-white/10 rounded-xl flex flex-col h-full overflow-hidden backdrop-blur-md">
        <div className="p-3.5 px-4 border-b border-white/10 flex items-center justify-between shrink-0">
          <div className="font-mono text-xs font-extrabold uppercase tracking-wider text-blue-500 flex items-center gap-1.5">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            Review Gate
          </div>
          <span className="font-mono text-[11px] font-bold bg-white/10 px-2 py-0.5 rounded-full text-slate-400">2</span>
        </div>
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-3">
          <KanbanCard priority="p0" badgeText="P0 · Review Gate" title="Zero-Leniency Audit SLA" description="Rigorous review of WebSocket PTY bridge, thread safety locks, and path traversal confinement." persona="Opus 4.6" status="Passed (100/100)" statusColor="#3b82f6" borderColor="rgba(59, 130, 246, 0.4)" />
          <KanbanCard priority="p1" badgeText="P1 · Review Gate" title="Polar.sh + x402 Header" description="Autonomous agent USDC micropayment verification and MoR webhook reconciliation." persona="Settlement" status="Pending" statusColor="#3b82f6" borderColor="rgba(59, 130, 246, 0.4)" />
        </div>
      </section>

      {/* Column 5: Shipped */}
      <section className="bg-[#12141d]/85 border border-white/10 rounded-xl flex flex-col h-full overflow-hidden backdrop-blur-md">
        <div className="p-3.5 px-4 border-b border-white/10 flex items-center justify-between shrink-0">
          <div className="font-mono text-xs font-extrabold uppercase tracking-wider text-emerald-500 flex items-center gap-1.5">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"></polyline></svg>
            Shipped (v2.8.0)
          </div>
          <span className="font-mono text-[11px] font-bold bg-white/10 px-2 py-0.5 rounded-full text-slate-400">17</span>
        </div>
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-3">
          <KanbanCard priority="done" badgeText="v2.8.0 Wave 8" title="Public Developer Documentation Portal (/docs)" description="Zero-AI-slop Obsidian docs portal with bespoke SVG visualizers, live hardware telemetry probe, and multi-language code snippets." persona="Route: /docs" status="Merged (3 New Tests)" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.4)" />
          <KanbanCard priority="done" badgeText="v2.7.0 Wave 7" title="Multi-Model DiT Engine Adapters" description="Polymorphic BaseVideoEngine, Wan2.1 (1.3B & 14B), HunyuanVideo, and FastMCP generation tools." persona="Commit: f0f5e74" status="Merged (24 New Tests)" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.4)" />
          <KanbanCard priority="done" badgeText="v2.7.0 Wave 7" title="In-Process Local Execution Drivers" description="Zero-cloud Kokoro-82M ONNX speech synthesis with -16 LUFS sidechaining, and GGUF screenplay deconstruction." persona="Commit: 3869f5e" status="Merged (9 New Tests)" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.4)" />
          <KanbanCard priority="done" badgeText="v2.6.0 Wave 6" title="Local GPU Inference & FastMCP Probe" description="Zero-dependency hardware probe, safety VRAM headroom calculation, curated model recommender, and 4 FastMCP tools." persona="Commit: 3fa854e" status="Merged (106/106 Tests)" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.4)" />
          <KanbanCard priority="done" badgeText="v2.6.0 Wave 6" title="Cockpit Local Compute HUD & Create Hybrid Switcher" description="Live Host hardware telemetry, 1-click model weight cache downloader, and dynamic $0.00 local cost telemetry." persona="Commit: Wave 6" status="Merged" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.4)" />
          <KanbanCard priority="done" badgeText="v2.5.0 Wave 5" title="SpacePilot Master Landing Page" description="SkyPilot-grade marketing homepage with live bidding terminal, 4-layer stack, and wholesale price matrix." persona="Commit: a386468" status="Merged" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.3)" />
          <KanbanCard priority="done" badgeText="v2.5.0 Wave 5" title="Cockpit OpenDesign Obsidian Overhaul" description="24px radius framed panels, live 1s billing odometer, and Multi-Cloud Provider Hub credential switcher." persona="Commit: 1beff14" status="Merged" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.3)" />
          <KanbanCard priority="done" badgeText="v2.5.0 Wave 5" title="Unified SVG Navigation & 3-Way Theme" description="Feather/Lucide SVG UI kit headers across all 5 pages with localStorage Dark/Light/System sync." persona="Commit: 93e399c" status="Merged" statusColor="#10b981" borderColor="rgba(16, 185, 129, 0.3)" />
        </div>
      </section>
    </main>
  );
}
