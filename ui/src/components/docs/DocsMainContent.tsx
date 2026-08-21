import { useState } from 'react';

export function DocsMainContent() {
  const [activeTab, setActiveTab] = useState<'json' | 'python'>('json');

  return (
    <main className="ml-0 md:ml-[280px] p-6 md:p-12 md:px-16 max-w-[900px] w-full">
      <section id="intro" className="mb-10">
        <h1 className="text-[2.5rem] font-semibold tracking-tight mb-4 mt-0">SpacePilot Developer Reference</h1>
        <p className="text-zinc-400 mb-5 leading-relaxed">The definitive technical reference for the SpacePilot high-performance video engine, local hardware bridging, and FastMCP agentic integration.</p>
      </section>

      {/* LIVE PROBE WIDGET */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6 my-8">
        <div className="flex justify-between items-center mb-4">
          <div className="font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block shadow-[0_0_8px_theme(colors.emerald.400)]"></span> 
            Local Compute Probe Active
          </div>
          <div className="text-xs text-zinc-500 uppercase m-0">Polling localhost:8080/api/compute</div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-black p-4 rounded-md border border-zinc-800">
            <div className="text-xs text-zinc-500 uppercase mb-1">Detected VRAM</div>
            <div className="text-xl font-semibold font-mono">-- GB</div>
          </div>
          <div className="bg-black p-4 rounded-md border border-zinc-800">
            <div className="text-xs text-zinc-500 uppercase mb-1">Active GPU</div>
            <div className="text-xl font-semibold font-mono">Scanning...</div>
          </div>
          <div className="bg-black p-4 rounded-md border border-zinc-800">
            <div className="text-xs text-zinc-500 uppercase mb-1">Recommended Engine</div>
            <div className="text-xl font-semibold font-mono">--</div>
          </div>
        </div>
      </div>

      <section id="quickstart" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">1. Quickstart</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">Zero-configuration local setup. We rely on Doppler for secrets management. Bypass the $0.30 SaaS markup and run your first $0.00 local inference in under 60 seconds.</p>
        
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden my-6">
          <div className="flex bg-zinc-950 border-b border-zinc-800 p-0">
            <button className="bg-zinc-900 text-zinc-50 font-medium border-none px-4 py-3 text-sm cursor-pointer border-r border-zinc-800 border-b-transparent -mb-[1px]">Terminal</button>
            <button className="ml-auto bg-transparent border-none text-zinc-400 hover:text-zinc-50 px-4 py-3 cursor-pointer text-sm transition-colors">Copy</button>
          </div>
          <pre className="p-4 overflow-x-auto font-mono text-sm text-zinc-50"><code className="language-bash">
{`# Install CLI and pull config
npm i -g @spacepilot/cli
doppler setup -p spacepilot -c dev_personal

# Run local hardware diagnostics and start daemon
doppler run -- spacepilot daemon start --port 8080`}
          </code></pre>
        </div>
      </section>

      <section id="architecture" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">2. Platform Architecture</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">SpacePilot utilizes a 4-Layer Composable Stack connecting your local editor via FastMCP to either a local Metal/CUDA runtime or a dynamically provisioned Spot Cloud instance based on the Headroom formula.</p>
        <p className="text-zinc-400 mb-5 leading-relaxed"><strong>Headroom Formula:</strong> <code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">H = VRAM_Total - (OS_Reserve + Model_Weights + KV_Cache + KV_Grad)</code></p>
        
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-8 my-8 flex justify-center overflow-x-auto">
            <svg width="600" height="300" viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg" className="min-w-[600px]">
                <rect x="50" y="20" width="500" height="260" rx="4" fill="#000" stroke="#27272a" />
                
                {/* Layer 1 */}
                <rect x="80" y="50" width="120" height="60" rx="4" fill="#000" stroke="#27272a" />
                <text x="140" y="80" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">Editor/IDE</text>
                <text x="140" y="95" textAnchor="middle" fill="#a1a1aa" fontSize="10">Cursor / Claude</text>
                
                <path d="M 200 80 L 260 80" stroke="#3b82f6" fill="none" markerEnd="url(#arrow)" strokeWidth="2" />
                
                {/* Layer 2 */}
                <rect x="260" y="50" width="120" height="60" rx="4" fill="#000" stroke="#27272a" />
                <text x="320" y="80" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">FastMCP Server</text>
                <text x="320" y="95" textAnchor="middle" fill="#a1a1aa" fontSize="10">stdio / HTTP</text>
                
                <path d="M 320 110 L 320 160" stroke="#3b82f6" fill="none" markerEnd="url(#arrow)" strokeWidth="2" />
                
                {/* Layer 3 */}
                <rect x="220" y="160" width="200" height="40" rx="4" fill="#000" stroke="#27272a" />
                <text x="320" y="185" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">Arbitrage Router</text>
                
                <path d="M 260 200 L 160 230" stroke="#3b82f6" fill="none" markerEnd="url(#arrow)" strokeWidth="2" />
                <path d="M 380 200 L 480 230" stroke="#3b82f6" fill="none" markerEnd="url(#arrow)" strokeWidth="2" />
                
                {/* Layer 4 Local */}
                <rect x="100" y="220" width="120" height="40" rx="4" fill="#000" stroke="#27272a" />
                <text x="160" y="245" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">Local GPU (H &gt; 0)</text>
                
                {/* Layer 4 Cloud */}
                <rect x="420" y="220" width="120" height="40" rx="4" fill="#000" stroke="#27272a" />
                <text x="480" y="245" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">Spot Cloud (H &lt; 0)</text>

                <defs>
                    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
                    </marker>
                </defs>
            </svg>
        </div>
      </section>

      <section id="models" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">3. Model Zoo & DiT Engines</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">Our tensor compilation targets the optimal precision for each underlying DiT architecture. Below is the engine capability matrix.</p>

        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-8 my-8 flex justify-center overflow-x-auto">
            <svg width="600" height="200" viewBox="0 0 600 200" xmlns="http://www.w3.org/2000/svg" className="min-w-[600px]">
                {/* Matrix Grid */}
                <line x1="150" y1="40" x2="150" y2="180" stroke="#27272a" strokeWidth="1"/>
                <line x1="300" y1="40" x2="300" y2="180" stroke="#27272a" strokeWidth="1"/>
                <line x1="450" y1="40" x2="450" y2="180" stroke="#27272a" strokeWidth="1"/>
                
                <line x1="20" y1="80" x2="580" y2="80" stroke="#27272a" strokeWidth="1"/>
                <line x1="20" y1="130" x2="580" y2="130" stroke="#27272a" strokeWidth="1"/>

                {/* Headers */}
                <text x="85" y="65" textAnchor="middle" fill="#fafafa" fontWeight="600" fontSize="12">Engine</text>
                <text x="225" y="65" textAnchor="middle" fill="#fafafa" fontWeight="600" fontSize="12">Architecture</text>
                <text x="375" y="65" textAnchor="middle" fill="#fafafa" fontWeight="600" fontSize="12">VRAM (bfloat16)</text>
                <text x="515" y="65" textAnchor="middle" fill="#fafafa" fontWeight="600" fontSize="12">Topology</text>

                {/* Row 1 */}
                <text x="85" y="110" textAnchor="middle" fill="#fafafa" fontSize="12">LTX-Video 2.5</text>
                <text x="225" y="110" textAnchor="middle" fill="#a1a1aa" fontSize="12">13B DiT</text>
                <text x="375" y="110" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">24 GB</text>
                <text x="515" y="110" textAnchor="middle" fill="#a1a1aa" fontSize="12">3D Causal VAE</text>

                {/* Row 2 */}
                <text x="85" y="160" textAnchor="middle" fill="#fafafa" fontSize="12">HunyuanVideo</text>
                <text x="225" y="160" textAnchor="middle" fill="#a1a1aa" fontSize="12">Dual-Stream DiT</text>
                <text x="375" y="160" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">40 GB+</text>
                <text x="515" y="160" textAnchor="middle" fill="#a1a1aa" fontSize="12">Flow Matching</text>
            </svg>
        </div>
      </section>

      <section id="audio" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">4. In-Process Audio Sidechain</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">Our pipeline features zero-latency in-memory audio sidechaining. We utilize an exact -16 LUFS integrated target, automatically ducking ambient tracks underneath voice (e.g., Kokoro TTS) using a fast lookahead compressor.</p>

        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-8 my-8 flex justify-center overflow-x-auto">
            <svg width="600" height="200" viewBox="0 0 600 200" xmlns="http://www.w3.org/2000/svg" className="min-w-[600px]">
                <rect x="50" y="40" width="100" height="40" rx="4" fill="#000" stroke="#27272a" />
                <text x="100" y="65" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">TTS / Voice</text>

                <rect x="50" y="120" width="100" height="40" rx="4" fill="#000" stroke="#27272a" />
                <text x="100" y="145" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">SFX / Music</text>

                <path d="M 150 60 L 250 60" stroke="#3b82f6" fill="none" markerEnd="url(#arrow)" strokeWidth="2" />
                <path d="M 150 140 L 200 140 L 200 110 L 250 110" stroke="#3b82f6" fill="none" markerEnd="url(#arrow)" strokeWidth="2" />
                <path d="M 200 60 L 200 90 L 250 90" stroke="#fbbf24" strokeWidth="2" strokeDasharray="4" markerEnd="url(#arrow_warn)" fill="none" />

                <rect x="250" y="50" width="120" height="80" rx="4" fill="#000" stroke="#27272a" />
                <text x="310" y="85" textAnchor="middle" fill="#fafafa" fontWeight="600" fontSize="12">Sidechain</text>
                <text x="310" y="105" textAnchor="middle" fill="#a1a1aa" fontSize="10">Ducker &amp; LUFS Calc</text>

                <path d="M 370 90 L 450 90" stroke="#3b82f6" fill="none" markerEnd="url(#arrow)" strokeWidth="2" />

                <rect x="450" y="70" width="100" height="40" rx="4" fill="#000" stroke="#27272a" />
                <text x="500" y="95" textAnchor="middle" fill="#fafafa" fontFamily="monospace" fontSize="12">Mixed (-16 LUFS)</text>
                
                <defs>
                    <marker id="arrow_warn" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#fbbf24" />
                    </marker>
                </defs>
            </svg>
        </div>
      </section>
      
      <section id="fastmcp" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">5. Agentic FastMCP Reference</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">Expose SpacePilot capabilities to your agent via FastMCP. The server provides robust schema validation for rendering DocIR 2.0 specs.</p>

        <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden my-6">
          <div className="flex bg-zinc-950 border-b border-zinc-800 p-0">
            <button 
              className={`border-none px-4 py-3 text-sm cursor-pointer border-r border-zinc-800 ${activeTab === 'json' ? 'bg-zinc-900 text-zinc-50 font-medium border-b-transparent -mb-[1px]' : 'bg-transparent text-zinc-400'}`}
              onClick={() => setActiveTab('json')}
            >
              JSON Schema
            </button>
            <button 
              className={`border-none px-4 py-3 text-sm cursor-pointer border-r border-zinc-800 ${activeTab === 'python' ? 'bg-zinc-900 text-zinc-50 font-medium border-b-transparent -mb-[1px]' : 'bg-transparent text-zinc-400'}`}
              onClick={() => setActiveTab('python')}
            >
              Python Config
            </button>
            <button className="ml-auto bg-transparent border-none text-zinc-400 hover:text-zinc-50 px-4 py-3 cursor-pointer text-sm transition-colors">Copy</button>
          </div>
          <pre className="p-4 overflow-x-auto font-mono text-sm text-zinc-50">
            {activeTab === 'json' ? (
              <code className="language-json">
{`{
  "name": "render_video",
  "description": "Submits a DocIR 2.0 payload to the rendering queue.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "prompt": { "type": "string" },
      "engine": { "type": "string", "enum": ["ltx-2.5", "hunyuan"] },
      "aspect_ratio": { "type": "string", "default": "16:9" }
    },
    "required": ["prompt"]
  }
}`}
              </code>
            ) : (
              <code className="language-python">
{`from fastmcp import FastMCP

mcp = FastMCP("SpacePilot")

@mcp.tool()
def render_video(prompt: str, engine: str = "ltx-2.5", aspect_ratio: str = "16:9") -> str:
    """Submits a DocIR 2.0 payload to the rendering queue."""
    # Internal routing logic
    return f"Job queued for {engine} at {aspect_ratio}"`}
              </code>
            )}
          </pre>
        </div>
      </section>

      <section id="rest-api" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">6. REST API & Auth Matrix</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">Direct HTTP access requires the <code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">X-Pluto-Token</code> header. API interactions are strictly typed.</p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse my-6 text-sm">
            <thead>
              <tr>
                <th className="p-3 text-left border-b border-zinc-800 font-semibold text-zinc-50 bg-zinc-950">Endpoint</th>
                <th className="p-3 text-left border-b border-zinc-800 font-semibold text-zinc-50 bg-zinc-950">Method</th>
                <th className="p-3 text-left border-b border-zinc-800 font-semibold text-zinc-50 bg-zinc-950">Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="p-3 text-left border-b border-zinc-800"><code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">/api/compute/local-profile</code></td>
                <td className="p-3 text-left border-b border-zinc-800">GET</td>
                <td className="p-3 text-left border-b border-zinc-800">Returns host hardware constraints.</td>
              </tr>
              <tr>
                <td className="p-3 text-left border-b border-zinc-800"><code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">/api/render/submit</code></td>
                <td className="p-3 text-left border-b border-zinc-800">POST</td>
                <td className="p-3 text-left border-b border-zinc-800">Accepts DocIR 2.0 payload.</td>
              </tr>
              <tr>
                <td className="p-3 text-left border-b border-zinc-800"><code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">/api/render/status/:id</code></td>
                <td className="p-3 text-left border-b border-zinc-800">GET</td>
                <td className="p-3 text-left border-b border-zinc-800">Polling endpoint for job completion.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section id="economics" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">7. SkyPilot Economics</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">SaaS APIs charge upwards of $0.30 per generation. Using our SkyPilot Spot Mesh router, generation requests that exceed your local headroom are automatically routed to spot instances (e.g., GCP a2-highgpu-1g preemptible) at roughly $0.012 per take, representing a 25x cost reduction.</p>
      </section>
      
      <div className="h-24"></div>
    </main>
  );
}
