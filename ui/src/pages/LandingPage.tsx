import { useState } from 'react';
import { 
  Radio, 
  ArrowRight, 
  Copy, 
  Check, 
  Play
} from 'lucide-react';

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState<'python' | 'fastmcp' | 'yaml' | 'curl'>('python');
  const [copied, setCopied] = useState(false);
  const [selectedTake, setSelectedTake] = useState(1);
  const [panAngle, setPanAngle] = useState(15);
  const [zoomLevel, setZoomLevel] = useState(1.4);

  const codeSnippets = {
    python: `from spacepilot import SpacePilotClient, CameraTrack

client = SpacePilotClient(base_url="http://127.0.0.1:8000")

# Dispatch 4-Take 2x2 generative exploration grid
session = client.cinema.generate(
    prompt="Cyberpunk neon alleyway, volumetric rain, anamorphic reflections",
    camera=CameraTrack(pan_deg=${panAngle}, zoom_ratio=${zoomLevel}x, roll_deg=0),
    num_takes=4,
    voice_preset="af_bella",
    music_lufs=-16.0,
    quantization="float8_e4m3fn"  # 0.0s resident cold start
)

print(f"Selected Take: {session.takes[0].video_url}")`,
    fastmcp: `{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "spacepilot_direct_scene",
    "arguments": {
      "prompt": "Cyberpunk neon alleyway, volumetric rain, anamorphic reflections",
      "camera_pan": ${panAngle},
      "camera_zoom": ${zoomLevel},
      "seed_stride": 1,
      "num_takes": 4,
      "lufs_target": -16.0
    }
  }
}`,
    yaml: `# spacepilot_spot.yaml (SkyPilot Orchestration Specification)
name: spacepilot-cinema-daemon

resources:
  accelerators: {L40S:1} # 48GB VRAM (Spot @ $0.75/hr)
  use_spot: true
  disk_size: 120

setup: |
  git clone https://github.com/motionvector-dev/pluto
  cd pluto && uv sync --frozen

run: |
  python -m pluto.daemon --model ltx-2.5-float8 --port 8000 --dead-man-timeout 30m`,
    curl: `curl -X POST http://127.0.0.1:8000/api/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "prompt": "Cyberpunk neon alleyway, volumetric rain",
    "takes": 4,
    "camera_pan": ${panAngle},
    "camera_zoom": ${zoomLevel},
    "seed": 42801
  }'`
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(codeSnippets[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-black text-[#fafafa] font-sans selection:bg-[#10b981]/30 selection:text-[#10b981]">
      {/* Background ambient lighting */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-b from-[#10b981]/12 via-[#06b6d4]/5 to-transparent blur-[140px]" />
      </div>

      {/* Navigation */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-black/70 border-b border-white/[0.08] px-6 lg:px-12 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl filter drop-shadow-[0_0_12px_rgba(16,185,129,0.5)]">🛸</span>
          <span className="font-extrabold text-[17px] tracking-tight flex items-center gap-2">
            SpacePilot
            <span className="font-mono text-[10px] font-bold bg-[#10b981]/15 border border-[#10b981]/40 text-[#10b981] px-2 py-0.5 rounded-full">
              v2.4.0
            </span>
          </span>
        </div>

        <div className="hidden md:flex items-center gap-7 text-[13.5px] font-medium text-[#a1a1aa]">
          <a href="#demo" className="hover:text-white transition-colors">Interactive Demo</a>
          <a href="#optimizer" className="hover:text-white transition-colors">GPU Matrix</a>
          <a href="#architecture" className="hover:text-white transition-colors">Architecture</a>
          <a href="#features" className="hover:text-white transition-colors">Pillars</a>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              navigator.clipboard.writeText('pip install spacepilot');
              alert('Copied to clipboard: pip install spacepilot');
            }}
            className="text-xs font-semibold bg-white text-black px-4 py-2 rounded-md hover:bg-[#e4e4e7] transition-all flex items-center gap-1.5 shadow-[0_0_20px_rgba(255,255,255,0.15)] cursor-pointer"
          >
            Get Started 🚀
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="relative z-10 pt-24 pb-16 px-6 max-w-6xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 bg-[#18181b] border border-white/[0.12] px-3.5 py-1.5 rounded-full font-mono text-xs text-[#a1a1aa] mb-8">
          <span className="w-2 h-2 rounded-full bg-[#10b981] shadow-[0_0_8px_#10b981]" />
          <span>SkyPilot for Cloud Compute · SpacePilot for Generative Cinema</span>
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.08] mb-6 bg-gradient-to-b from-white via-white to-[#a1a1aa] bg-clip-text text-transparent">
          The Autonomous Cinema Workstation<br className="hidden sm:block" /> for AI Agents & Directors.
        </h1>

        <p className="text-lg sm:text-xl text-[#a1a1aa] max-w-3xl mx-auto mb-10 leading-relaxed">
          Zero cold starts. <strong className="text-white font-semibold">Resident LTX-2.5 Quantized Float8</strong> on 48GB VRAM, in-process <strong className="text-white font-semibold">Kokoro-82M Voice Mastering</strong> (-16 LUFS), and sub-second multi-cloud spot arbitrage across AWS & Shadeform.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4 mb-16">
          <button 
            onClick={() => {
              navigator.clipboard.writeText('pip install spacepilot && sky launch spacepilot.yaml');
              alert('Copied to clipboard: pip install spacepilot && sky launch spacepilot.yaml');
            }}
            className="bg-white text-black font-bold text-sm px-7 py-3.5 rounded-lg hover:bg-[#e4e4e7] transition-all flex items-center gap-2 shadow-[0_0_30px_rgba(255,255,255,0.2)] hover:translate-y-[-1px] cursor-pointer"
          >
            <span>Quickstart CLI (`pip install spacepilot`)</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <a 
            href="#architecture"
            className="bg-[#18181b] hover:bg-[#222226] border border-white/[0.12] text-white font-semibold text-sm px-6 py-3.5 rounded-lg transition-all flex items-center gap-2"
          >
            🛸 View FastMCP Specs
          </a>
        </div>

        {/* Mem0-Style Side-by-Side Interactive Workstation Demo */}
        <section id="demo" className="bg-[#09090b] border border-white/[0.14] rounded-2xl overflow-hidden shadow-2xl text-left mb-24">
          <div className="bg-[#111114] px-5 py-3.5 border-b border-white/[0.08] flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-white/[0.15]" />
                <div className="w-2.5 h-2.5 rounded-full bg-white/[0.15]" />
                <div className="w-2.5 h-2.5 rounded-full bg-white/[0.15]" />
              </div>
              <span className="font-mono text-xs text-[#71717a] ml-2 font-medium">spacepilot-director-engine · L40S 48GB (AWS Spot $0.75/hr)</span>
            </div>

            {/* Code Tabs */}
            <div className="flex items-center gap-1 bg-black/60 p-1 rounded-lg border border-white/[0.08]">
              {(['python', 'fastmcp', 'yaml', 'curl'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                    activeTab === tab 
                      ? 'bg-[#18181b] text-white font-semibold border border-white/[0.12] shadow-sm' 
                      : 'text-[#71717a] hover:text-white'
                  }`}
                >
                  {tab === 'python' ? 'Python SDK' : tab === 'fastmcp' ? 'FastMCP Tool' : tab === 'yaml' ? 'SkyPilot YAML' : 'cURL'}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
            {/* Left: Code Box */}
            <div className="lg:col-span-6 p-6 bg-black font-mono text-xs leading-relaxed overflow-x-auto relative border-b lg:border-b-0 lg:border-r border-white/[0.08]">
              <button 
                onClick={handleCopy}
                className="absolute top-4 right-4 p-2 bg-[#18181b] hover:bg-[#222226] border border-white/[0.1] rounded-md text-[#a1a1aa] hover:text-white transition-all cursor-pointer"
                title="Copy snippet"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-[#10b981]" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
              <pre className="text-[#38bdf8] whitespace-pre font-mono">
                {codeSnippets[activeTab]}
              </pre>
            </div>

            {/* Right: Live Canvas & 2x2 Director Grid */}
            <div className="lg:col-span-6 p-6 bg-[#09090b] flex flex-col justify-between gap-6">
              {/* Interactive Camera Controls */}
              <div className="grid grid-cols-2 gap-4 bg-[#111114] p-4 rounded-xl border border-white/[0.08]">
                <div>
                  <div className="flex justify-between text-xs font-mono text-[#a1a1aa] mb-2">
                    <span>Camera Pan</span>
                    <span className="text-[#10b981] font-bold">+{panAngle}°</span>
                  </div>
                  <input 
                    type="range" 
                    min="-45" 
                    max="45" 
                    value={panAngle} 
                    onChange={(e) => setPanAngle(Number(e.target.value))}
                    className="w-full accent-[#10b981] cursor-pointer"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs font-mono text-[#a1a1aa] mb-2">
                    <span>Camera Zoom</span>
                    <span className="text-[#06b6d4] font-bold">{zoomLevel}x</span>
                  </div>
                  <input 
                    type="range" 
                    min="1.0" 
                    max="2.5" 
                    step="0.1"
                    value={zoomLevel} 
                    onChange={(e) => setZoomLevel(Number(e.target.value))}
                    className="w-full accent-[#06b6d4] cursor-pointer"
                  />
                </div>
              </div>

              {/* 2x2 Take Matrix */}
              <div className="grid grid-cols-2 gap-3">
                {[1, 2, 3, 4].map((take) => (
                  <div 
                    key={take}
                    onClick={() => setSelectedTake(take)}
                    className={`cursor-pointer bg-[#111114] rounded-xl p-3.5 border transition-all flex flex-col justify-between aspect-video relative overflow-hidden ${
                      selectedTake === take 
                        ? 'border-[#10b981] shadow-[0_0_20px_rgba(16,185,129,0.25)] bg-[#111114]/90' 
                        : 'border-white/[0.08] hover:border-white/[0.2]'
                    }`}
                  >
                    <div className="flex justify-between items-center z-10">
                      <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-black/80 border border-white/[0.08]">
                        TAKE {take} · SEED {42800 + take}
                      </span>
                      {selectedTake === take && (
                        <span className="font-mono text-[9px] font-bold text-[#10b981] bg-[#10b981]/15 px-1.5 py-0.5 rounded border border-[#10b981]/40">
                          DIRECTOR PICK
                        </span>
                      )}
                    </div>
                    
                    <div className="flex justify-between items-end font-mono text-[10px] text-[#71717a] z-10">
                      <span>Pan: +{panAngle}°</span>
                      <span className="text-white flex items-center gap-1">
                        <Play className="w-2.5 h-2.5 fill-white" /> 4.0s
                      </span>
                    </div>

                    {/* Subtle video aesthetic backdrop */}
                    <div className="absolute inset-0 bg-gradient-to-tr from-black via-transparent to-white/[0.02]" />
                  </div>
                ))}
              </div>

              {/* Kokoro Audio Meter Bar */}
              <div className="bg-[#111114] px-4 py-2.5 rounded-lg border border-white/[0.08] flex items-center justify-between font-mono text-xs text-[#a1a1aa]">
                <div className="flex items-center gap-2">
                  <Radio className="w-3.5 h-3.5 text-[#10b981]" />
                  <span>Kokoro-82M Voice (af_bella):</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex gap-0.5">
                    {[40, 60, 75, 90, 65, 45, 80, 70, 85, 95, 55, 30].map((h, i) => (
                      <div 
                        key={i} 
                        className="w-1 bg-[#10b981] rounded-full" 
                        style={{ height: `${h * 0.16}px` }} 
                      />
                    ))}
                  </div>
                  <span className="text-[#10b981] font-bold ml-2">-16.0 LUFS</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </header>

      {/* SkyPilot-Inspired Multi-Cloud GPU Matrix */}
      <section id="optimizer" className="py-20 px-6 max-w-6xl mx-auto border-t border-white/[0.08]">
        <div className="text-center mb-16">
          <span className="font-mono text-xs font-bold text-[#10b981] uppercase tracking-wider block mb-3">
            SkyPilot Cost Arbitrage & Benchmarks
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-4">
            Spend Less on Compute. Iterate 10× Faster.
          </h2>
          <p className="text-[#a1a1aa] max-w-2xl mx-auto">
            Traditional containers force 45s cold starts for every render. SpacePilot keeps a 0.0s resident daemon alive with automated dead-man auto-termination.
          </p>
        </div>

        <div className="bg-[#09090b] border border-white/[0.12] rounded-xl overflow-hidden shadow-xl mb-12">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#111114] border-b border-white/[0.08] font-mono text-xs text-[#71717a] uppercase">
                <tr>
                  <th className="p-4 pl-6">Cloud Fleet / Hardware</th>
                  <th className="p-4">VRAM / Accelerator</th>
                  <th className="p-4">Hourly Cost</th>
                  <th className="p-4">Cold Start</th>
                  <th className="p-4 pr-6">Direct Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06] text-[#a1a1aa] font-mono text-xs">
                <tr className="hover:bg-white/[0.02] bg-[#10b981]/[0.02]">
                  <td className="p-4 pl-6 font-sans font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#10b981]" />
                    AWS Spot Direct (g6e.xlarge)
                  </td>
                  <td className="p-4 text-white">48GB L40S</td>
                  <td className="p-4 text-[#10b981] font-bold">~$0.75 / hr</td>
                  <td className="p-4 text-[#10b981] font-bold">0.0s (Resident)</td>
                  <td className="p-4 pr-6">
                    <span className="bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/40 px-2.5 py-1 rounded font-bold">
                      ⭐ Recommended
                    </span>
                  </td>
                </tr>
                <tr className="hover:bg-white/[0.02]">
                  <td className="p-4 pl-6 font-sans font-medium text-white">Shadeform 20+ Cloud Mesh</td>
                  <td className="p-4">48GB / 80GB A100</td>
                  <td className="p-4 font-bold text-white">~$0.89 / hr</td>
                  <td className="p-4 text-[#10b981]">0.0s (Resident)</td>
                  <td className="p-4 pr-6 text-[#71717a]">Auto-Failover</td>
                </tr>
                <tr className="hover:bg-white/[0.02]">
                  <td className="p-4 pl-6 font-sans font-medium text-white">Local Homelab (Apple Silicon M3/M4)</td>
                  <td className="p-4">36GB–128GB Unified</td>
                  <td className="p-4 text-[#10b981] font-bold">$0.00 / hr</td>
                  <td className="p-4 text-[#10b981]">0.0s (Resident)</td>
                  <td className="p-4 pr-6 text-[#71717a]">Local Mock</td>
                </tr>
                <tr className="hover:bg-white/[0.02] text-[#71717a]">
                  <td className="p-4 pl-6 font-sans">Legacy Serverless Video APIs</td>
                  <td className="p-4">Black Box</td>
                  <td className="p-4 text-[#f43f5e] font-bold">$0.10–$0.50 / gen</td>
                  <td className="p-4 text-[#f43f5e] font-bold">35s–60s Latency</td>
                  <td className="p-4 pr-6 text-[#f43f5e]">High Markup</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FastMCP Agent Directing Topology */}
      <section id="architecture" className="py-20 px-6 max-w-6xl mx-auto border-t border-white/[0.08]">
        <div className="text-center mb-16">
          <span className="font-mono text-xs font-bold text-[#a855f7] uppercase tracking-wider block mb-3">
            Autonomous Directing Protocol
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-4">
            Direct Cinema with Code, CLI, or FastMCP Agents
          </h2>
          <p className="text-[#a1a1aa] max-w-2xl mx-auto">
            Connect Claude, Cursor, Antigravity, or custom agents directly into the SpacePilot tool suite.
          </p>
        </div>

        <div className="bg-[#09090b] border border-white/[0.12] rounded-xl p-8 font-mono text-xs leading-relaxed overflow-x-auto shadow-2xl mb-16 text-[#38bdf8]">
          <pre>{`┌───────────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────────┐
│   Autonomous AI Agents    │      │    FastMCP Tool Server    │      │  Resident Cinema Runtime  │
│  (Claude / Cursor / Grok) │ ───> │  (src/pluto_mcp_server)   │ ───> │  (LTX-2.5 + Kokoro 48GB)  │
└───────────────────────────┘      └───────────────────────────┘      └───────────────────────────┘
              │                                  │                                  │
              ▼                                  ▼                                  ▼
┌───────────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────────┐
│  Interactive Cockpit PTY  │      │ SkyPilot Spot Orchestrator│      │   ProRes 422 Mastering    │
│ (Web SSH / nvidia-smi)    │      │ (AWS Spot & Shadeform)    │      │ (Dual Keyframes + -16LUFS)│
└───────────────────────────┘      └───────────────────────────┘      └───────────────────────────┘`}</pre>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.08] py-12 px-6 bg-black text-xs text-[#71717a]">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <span className="text-lg">🛸</span>
            <span className="font-bold text-white">SpacePilot.dev</span>
            <span>· Generative Cinema Workstation</span>
          </div>

          <div className="flex items-center gap-6 font-medium">
            <a href="#demo" className="hover:text-white transition-colors">Interactive Demo</a>
            <a href="#optimizer" className="hover:text-white transition-colors">GPU Matrix</a>
            <a href="https://motionvector.dev" className="hover:text-white transition-colors">MotionVector</a>
            <a href="https://github.com/motionvector-dev/pluto" className="hover:text-white transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
