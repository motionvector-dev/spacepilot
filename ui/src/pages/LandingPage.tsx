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
    <div className="min-h-screen bg-ground text-ink font-sans selection:bg-verify/30 selection:text-verify">
      {/* Background ambient lighting */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-white/[0.06] blur-[140px]" />
      </div>

      {/* Navigation */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-ground/70 border-b border-line-200 px-6 lg:px-12 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl">🛸</span>
          <span className="font-extrabold text-[17px] tracking-tight flex items-center gap-2">
            SpacePilot
            <span className="font-mono text-[10px] font-bold bg-verify-soft border border-verify/40 text-verify px-2 py-0.5 rounded-full">
              v2.4.0
            </span>
          </span>
        </div>

        <div className="hidden md:flex items-center gap-7 text-[13.5px] font-medium text-ink-900">
          <a href="#demo" className="hover:text-ink transition-colors">Interactive Demo</a>
          <a href="#optimizer" className="hover:text-ink transition-colors">GPU Matrix</a>
          <a href="#architecture" className="hover:text-ink transition-colors">Architecture</a>
          <a href="#features" className="hover:text-ink transition-colors">Pillars</a>
        </div>

        <div className="flex items-center gap-3">
          <a 
            href="https://github.com/motionvector-dev/pluto" 
            target="_blank" 
            rel="noreferrer"
            className="hidden sm:flex items-center gap-1.5 text-xs font-mono bg-inset hover:bg-strong border border-line-200 px-3 py-1.5 rounded-md text-ink-900 hover:text-ink transition-all"
          >
            ★ 10.4k
          </a>
          <button 
            onClick={() => {
              navigator.clipboard.writeText('pip install spacepilot');
              alert('Copied to clipboard: pip install spacepilot');
            }}
            className="text-xs font-semibold bg-accent text-accent-contrast px-4 py-2 rounded-md hover:opacity-90 transition-all flex items-center gap-1.5 cursor-pointer"
          >
            Get Started 🚀
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="relative z-10 pt-24 pb-16 px-6 max-w-6xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 bg-inset border border-line-300 px-3.5 py-1.5 rounded-full font-mono text-xs text-ink-900 mb-8">
          <span className="w-2 h-2 rounded-full bg-verify" />
          <span>SkyPilot for Cloud Compute · SpacePilot for Generative Cinema</span>
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.08] mb-6 bg-gradient-to-b from-ink via-ink to-ink-700 bg-clip-text text-transparent">
          The Autonomous Cinema Workstation<br className="hidden sm:block" /> for AI Agents & Directors.
        </h1>

        <p className="text-lg sm:text-xl text-ink-900 max-w-3xl mx-auto mb-10 leading-relaxed">
          Zero cold starts. <strong className="text-ink font-semibold">Resident LTX-2.5 Quantized Float8</strong> on 48GB VRAM, in-process <strong className="text-ink font-semibold">Kokoro-82M Voice Mastering</strong> (-16 LUFS), and sub-second multi-cloud spot arbitrage across AWS & Shadeform.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4 mb-16">
          <button 
            onClick={() => {
              navigator.clipboard.writeText('pip install spacepilot && sky launch spacepilot.yaml');
              alert('Copied to clipboard: pip install spacepilot && sky launch spacepilot.yaml');
            }}
            className="bg-accent text-accent-contrast font-bold text-sm px-7 py-3.5 rounded-lg hover:opacity-90 transition-all flex items-center gap-2 hover:translate-y-[-1px] cursor-pointer"
          >
            <span>Quickstart CLI (`pip install spacepilot`)</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <a 
            href="#architecture"
            className="bg-inset hover:bg-strong border border-line-300 text-ink font-semibold text-sm px-6 py-3.5 rounded-lg transition-all flex items-center gap-2"
          >
            🛸 View FastMCP Specs
          </a>
        </div>

        {/* Mem0-Style Side-by-Side Interactive Workstation Demo */}
        <section id="demo" className="bg-surface border border-line-300 rounded-2xl overflow-hidden shadow-lg text-left mb-24">
          <div className="bg-raised px-5 py-3.5 border-b border-line-200 flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-strong" />
                <div className="w-2.5 h-2.5 rounded-full bg-strong" />
                <div className="w-2.5 h-2.5 rounded-full bg-strong" />
              </div>
              <span className="font-mono text-xs text-ink-500 ml-2 font-medium">spacepilot-director-engine · L40S 48GB (AWS Spot $0.75/hr)</span>
            </div>

            {/* Code Tabs */}
            <div className="flex items-center gap-1 bg-inset p-1 rounded-lg border border-line-200">
              {(['python', 'fastmcp', 'yaml', 'curl'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                    activeTab === tab 
                      ? 'bg-strong text-ink font-semibold border border-line-300 shadow-sm'
                      : 'text-ink-500 hover:text-ink'
                  }`}
                >
                  {tab === 'python' ? 'Python SDK' : tab === 'fastmcp' ? 'FastMCP Tool' : tab === 'yaml' ? 'SkyPilot YAML' : 'cURL'}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
            {/* Left: Code Box */}
            <div className="lg:col-span-6 p-6 bg-ground font-mono text-xs leading-relaxed overflow-x-auto relative border-b lg:border-b-0 lg:border-r border-line-200">
              <button 
                onClick={handleCopy}
                className="absolute top-4 right-4 p-2 bg-inset hover:bg-strong border border-line-200 rounded-md text-ink-900 hover:text-ink transition-all cursor-pointer"
                title="Copy snippet"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-verify" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
              <pre className="text-ink-900 whitespace-pre font-mono">
                {codeSnippets[activeTab]}
              </pre>
            </div>

            {/* Right: Live Canvas & 2x2 Director Grid */}
            <div className="lg:col-span-6 p-6 bg-surface flex flex-col justify-between gap-6">
              {/* Interactive Camera Controls */}
              <div className="grid grid-cols-2 gap-4 bg-raised p-4 rounded-xl border border-line-200">
                <div>
                  <div className="flex justify-between text-xs font-mono text-ink-900 mb-2">
                    <span>Camera Pan</span>
                    <span className="text-verify font-bold">+{panAngle}°</span>
                  </div>
                  <input 
                    type="range" 
                    min="-45" 
                    max="45" 
                    value={panAngle} 
                    onChange={(e) => setPanAngle(Number(e.target.value))}
                    className="w-full accent-verify cursor-pointer"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs font-mono text-ink-900 mb-2">
                    <span>Camera Zoom</span>
                    <span className="text-ink-900 font-bold">{zoomLevel}x</span>
                  </div>
                  <input 
                    type="range" 
                    min="1.0" 
                    max="2.5" 
                    step="0.1"
                    value={zoomLevel} 
                    onChange={(e) => setZoomLevel(Number(e.target.value))}
                    className="w-full accent-ink-700 cursor-pointer"
                  />
                </div>
              </div>

              {/* 2x2 Take Matrix */}
              <div className="grid grid-cols-2 gap-3">
                {[1, 2, 3, 4].map((take) => (
                  <div 
                    key={take}
                    onClick={() => setSelectedTake(take)}
                    className={`cursor-pointer bg-raised rounded-xl p-3.5 border transition-all flex flex-col justify-between aspect-video relative overflow-hidden ${
                      selectedTake === take
                        ? 'border-verify bg-raised'
                        : 'border-line-200 hover:border-line-400'
                    }`}
                  >
                    <div className="flex justify-between items-center z-10">
                      <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-inset border border-line-200">
                        TAKE {take} · SEED {42800 + take}
                      </span>
                      {selectedTake === take && (
                        <span className="font-mono text-[9px] font-bold text-verify bg-verify-soft px-1.5 py-0.5 rounded border border-verify/40">
                          DIRECTOR PICK
                        </span>
                      )}
                    </div>
                    
                    <div className="flex justify-between items-end font-mono text-[10px] text-ink-500 z-10">
                      <span>Pan: +{panAngle}°</span>
                      <span className="text-ink flex items-center gap-1">
                        <Play className="w-2.5 h-2.5 fill-current" /> 4.0s
                      </span>
                    </div>

                    {/* Subtle video aesthetic backdrop */}
                    
                  </div>
                ))}
              </div>

              {/* Kokoro Audio Meter Bar */}
              <div className="bg-raised px-4 py-2.5 rounded-lg border border-line-200 flex items-center justify-between font-mono text-xs text-ink-900">
                <div className="flex items-center gap-2">
                  <Radio className="w-3.5 h-3.5 text-verify" />
                  <span>Kokoro-82M Voice (af_bella):</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex gap-0.5">
                    {[40, 60, 75, 90, 65, 45, 80, 70, 85, 95, 55, 30].map((h, i) => (
                      <div 
                        key={i} 
                        className="w-1 bg-verify rounded-full" 
                        style={{ height: `${h * 0.16}px` }} 
                      />
                    ))}
                  </div>
                  <span className="text-verify font-bold ml-2">-16.0 LUFS</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </header>

      {/* SkyPilot-Inspired Multi-Cloud GPU Matrix */}
      <section id="optimizer" className="py-20 px-6 max-w-6xl mx-auto border-t border-line-200">
        <div className="text-center mb-16">
          <span className="font-mono text-xs font-bold text-verify uppercase tracking-wider block mb-3">
            SkyPilot Cost Arbitrage & Benchmarks
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-4">
            Spend Less on Compute. Iterate 10× Faster.
          </h2>
          <p className="text-ink-900 max-w-2xl mx-auto">
            Traditional containers force 45s cold starts for every render. SpacePilot keeps a 0.0s resident daemon alive with automated dead-man auto-termination.
          </p>
        </div>

        <div className="bg-surface border border-line-300 rounded-xl overflow-hidden mb-12">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-raised border-b border-line-200 font-mono text-xs text-ink-500 uppercase">
                <tr>
                  <th className="p-4 pl-6">Cloud Fleet / Hardware</th>
                  <th className="p-4">VRAM / Accelerator</th>
                  <th className="p-4">Hourly Cost</th>
                  <th className="p-4">Cold Start</th>
                  <th className="p-4 pr-6">Direct Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-100 text-ink-900 font-mono text-xs">
                <tr className="hover:bg-raised bg-verify-soft">
                  <td className="p-4 pl-6 font-sans font-bold text-ink flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-verify" />
                    AWS Spot Direct (g6e.xlarge)
                  </td>
                  <td className="p-4 text-ink">48GB L40S</td>
                  <td className="p-4 text-verify font-bold">~$0.75 / hr</td>
                  <td className="p-4 text-verify font-bold">0.0s (Resident)</td>
                  <td className="p-4 pr-6">
                    <span className="bg-verify-soft text-verify border border-verify/40 px-2.5 py-1 rounded font-bold">
                      ⭐ Recommended
                    </span>
                  </td>
                </tr>
                <tr className="hover:bg-raised">
                  <td className="p-4 pl-6 font-sans font-medium text-ink">Shadeform 20+ Cloud Mesh</td>
                  <td className="p-4">48GB / 80GB A100</td>
                  <td className="p-4 font-bold text-ink">~$0.89 / hr</td>
                  <td className="p-4 text-verify">0.0s (Resident)</td>
                  <td className="p-4 pr-6 text-ink-500">Auto-Failover</td>
                </tr>
                <tr className="hover:bg-raised">
                  <td className="p-4 pl-6 font-sans font-medium text-ink">Local Homelab (Apple Silicon M3/M4)</td>
                  <td className="p-4">36GB–128GB Unified</td>
                  <td className="p-4 text-verify font-bold">$0.00 / hr</td>
                  <td className="p-4 text-verify">0.0s (Resident)</td>
                  <td className="p-4 pr-6 text-ink-500">Local Mock</td>
                </tr>
                <tr className="hover:bg-raised text-ink-500">
                  <td className="p-4 pl-6 font-sans">Legacy Serverless Video APIs</td>
                  <td className="p-4">Black Box</td>
                  <td className="p-4 text-danger font-bold">$0.10–$0.50 / gen</td>
                  <td className="p-4 text-danger font-bold">35s–60s Latency</td>
                  <td className="p-4 pr-6 text-danger">High Markup</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FastMCP Agent Directing Topology */}
      <section id="architecture" className="py-20 px-6 max-w-6xl mx-auto border-t border-line-200">
        <div className="text-center mb-16">
          <span className="font-mono text-xs font-bold text-ink-500 uppercase tracking-wider block mb-3">
            Autonomous Directing Protocol
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-4">
            Direct Cinema with Code, CLI, or FastMCP Agents
          </h2>
          <p className="text-ink-900 max-w-2xl mx-auto">
            Connect Claude, Cursor, Antigravity, or custom agents directly into the SpacePilot tool suite.
          </p>
        </div>

        <div className="bg-surface border border-line-300 rounded-xl p-8 font-mono text-xs leading-relaxed overflow-x-auto mb-16 text-ink-900">
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
      <footer className="border-t border-line-200 py-12 px-6 bg-ground text-xs text-ink-500">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <span className="text-lg">🛸</span>
            <span className="font-bold text-ink">SpacePilot.dev</span>
            <span>· Generative Cinema Workstation</span>
          </div>

          <div className="flex items-center gap-6 font-medium">
            <a href="#demo" className="hover:text-ink transition-colors">Interactive Demo</a>
            <a href="#optimizer" className="hover:text-ink transition-colors">GPU Matrix</a>
            <a href="https://motionvector.dev" className="hover:text-ink transition-colors">MotionVector</a>
            <a href="https://github.com/motionvector-dev/pluto" className="hover:text-ink transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
