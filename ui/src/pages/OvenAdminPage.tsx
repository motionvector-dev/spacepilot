import { 
  ShieldCheck,
  Activity
} from 'lucide-react';

export default function OvenAdminPage() {
  const lanes = [
    {
      title: 'Backburner',
      count: 3,
      color: 'text-[#71717a]',
      cards: [
        { badge: 'P2 · Horizon 4', title: '4D Gaussian Splatting', desc: 'Volumetric light fields & spatial video rendering for Apple Vision Pro / Meta Quest 3.', persona: 'Research' },
        { badge: 'P2 · Horizon 5', title: '60 FPS StreamDiffusion', desc: 'Sub-50ms WebRTC interactive latent streaming with real-time 3D camera joystick.', persona: 'Realtime' },
        { badge: 'P2 · Horizon 5', title: 'Bio & Protein Surrogates', desc: 'AlphaFold / ESMFold ONNX CUDA execution pipelines on spot GPU hardware.', persona: 'Science' }
      ]
    },
    {
      title: 'Planned',
      count: 3,
      color: 'text-[#a855f7]',
      cards: [
        { badge: 'P1 · Wave 4/5', title: '1-Click LoRA Studio', desc: 'Upload 10-20 reference images in Cockpit, run spot PEFT training ($0.40), hot-swap adapter.', persona: 'LoRA Agent' },
        { badge: 'P1 · Wave 4/5', title: 'Spot Training & R2 Sync', desc: 'Multi-node training recipes with preemption recovery and loss curve telemetry streaming.', persona: 'MLOps' },
        { badge: 'P1 · Wave 4/5', title: 'Top Model Leaderboard Recipes', desc: '1-click hardware allocation recipes for Wan2.1, HunyuanVideo, DeepSeek-R1, and Qwen2.5-VL.', persona: 'Catalog' }
      ]
    },
    {
      title: 'Cooking (In-Flight)',
      count: 2,
      color: 'text-[#f59e0b]',
      highlight: true,
      cards: [
        { badge: 'P0 · Wave 5 Frontend', title: 'SpacePilot.dev Flagship & Studio React Redo', desc: 'React 19 + TypeScript + Vite 6 + Tailwind v4 refactor. 2×2 Director Take Canvas, Kokoro waveform audio meter, and internal admin oven board.', persona: 'Frontend Agent (pluto-frontend)', statusColor: 'text-[#10b981]' },
        { badge: 'P0 · Wave 5 Backend', title: 'FastAPI Modular Package Refactor (src/pluto)', desc: 'Surgically split 2,577-line studio_api.py into core/config.py, app.py, and modular api/routes & services with 139-test green gate.', persona: 'Backend Agent (pluto-backend)', statusColor: 'text-[#f59e0b]' }
      ]
    },
    {
      title: 'Review Gate',
      count: 2,
      color: 'text-[#38bdf8]',
      cards: [
        { badge: 'P0 · Review Gate', title: 'Zero-Leniency Audit SLA', desc: 'Rigorous review of WebSocket PTY bridge, thread safety locks, and path traversal confinement.', persona: 'Opus 4.6 (100/100)' },
        { badge: 'P1 · Review Gate', title: 'Polar.sh + x402 Header', desc: 'Autonomous agent USDC micropayment verification and MoR webhook reconciliation.', persona: 'Settlement' }
      ]
    },
    {
      title: 'Shipped (v2.8.0)',
      count: 17,
      color: 'text-[#10b981]',
      cards: [
        { badge: 'v2.8.0 Wave 8', title: 'Public Developer Docs Portal (/docs)', desc: 'Zero-AI-slop Obsidian docs portal with bespoke SVG visualizers, live hardware telemetry probe, and multi-language snippets.', persona: 'Merged (142 Tests Green)' },
        { badge: 'v2.7.0 Wave 7', title: 'Multi-Model DiT Engine Adapters', desc: 'Polymorphic BaseVideoEngine, Wan2.1 (1.3B & 14B), HunyuanVideo, and FastMCP generation tools.', persona: 'Merged (Commit: f0f5e74)' }
      ]
    }
  ];

  return (
    <div className="min-h-screen bg-black text-[#fafafa] flex flex-col font-sans">
      {/* Oven Header */}
      <header className="h-16 bg-[#09090b] border-b border-white/[0.08] px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#f59e0b]/15 border border-[#f59e0b]/40 flex items-center justify-center text-base">
            🔥
          </div>
          <div>
            <div className="flex items-center gap-2 font-extrabold text-sm tracking-tight">
              <span>SpacePilot · Oven Internal Admin</span>
              <span className="text-[10px] font-mono font-bold bg-[#f59e0b]/15 text-[#f59e0b] border border-[#f59e0b]/30 px-2 py-0.5 rounded">
                ADLC SWARM v2.8.0
              </span>
            </div>
            <div className="text-[11px] font-mono text-[#71717a]">
              Parallel Worktrees: <span className="text-[#10b981]">pluto-frontend</span> &amp; <span className="text-[#f59e0b]">pluto-backend</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="flex items-center gap-2 bg-[#111114] border border-white/[0.08] px-3 py-1.5 rounded-md text-[#a1a1aa]">
            <Activity className="w-3.5 h-3.5 text-[#10b981]" />
            <span>Swarms: <strong className="text-white">2 Active (Worktrees)</strong></span>
          </div>
          <div className="flex items-center gap-2 bg-[#111114] border border-white/[0.08] px-3 py-1.5 rounded-md text-[#a1a1aa]">
            <ShieldCheck className="w-3.5 h-3.5 text-[#10b981]" />
            <span>Tests: <strong className="text-[#10b981]">142/142 (100% Green)</strong></span>
          </div>
        </div>
      </header>

      {/* 5-Lane Full Viewport Kanban Matrix */}
      <main className="flex-1 p-6 grid grid-cols-1 md:grid-cols-5 gap-4 overflow-x-auto">
        {lanes.map((lane, idx) => (
          <section key={idx} className="bg-[#09090b] border border-white/[0.08] rounded-xl flex flex-col overflow-hidden">
            <div className="p-3.5 border-b border-white/[0.08] bg-[#111114] flex items-center justify-between font-mono text-xs">
              <span className={`font-bold uppercase tracking-wider flex items-center gap-1.5 ${lane.color}`}>
                {lane.title}
              </span>
              <span className="font-bold bg-white/[0.06] text-[#a1a1aa] px-2 py-0.5 rounded-full text-[10px]">
                {lane.count}
              </span>
            </div>

            <div className="p-3 flex-1 flex flex-col gap-3 overflow-y-auto">
              {lane.cards.map((card, cIdx) => (
                <div 
                  key={cIdx} 
                  className={`bg-[#111114] border rounded-lg p-3.5 flex flex-col gap-2 transition-all hover:bg-[#18181b] ${
                    lane.highlight ? 'border-[#f59e0b]/40 shadow-[0_0_16px_rgba(245,158,11,0.1)]' : 'border-white/[0.06] hover:border-white/[0.14]'
                  }`}
                >
                  <span className="font-mono text-[9px] font-bold text-[#a1a1aa] bg-white/[0.04] border border-white/[0.08] px-2 py-0.5 rounded self-start">
                    {card.badge}
                  </span>
                  <div className="text-xs font-bold text-white leading-snug">
                    {card.title}
                  </div>
                  <div className="text-[11px] text-[#a1a1aa] leading-relaxed">
                    {card.desc}
                  </div>
                  <div className="pt-2 border-t border-white/[0.04] flex items-center justify-between font-mono text-[10px] text-[#71717a]">
                    <span>{card.persona}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </main>
    </div>
  );
}
