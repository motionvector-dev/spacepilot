import { useState } from 'react';
import { useComputeProfile, useRecommendedModels } from '../../hooks/useCompute';

export function DocsMainContent() {
  const [activeTab, setActiveTab] = useState<'json' | 'python'>('json');
  const { data: profile, isError: isProfileError } = useComputeProfile();
  const { data: models } = useRecommendedModels();

  const recommendedEngine = models && models.length > 0 ? models[0].name : (profile?.is_mps ? 'LTX-2.5 (Float8)' : 'Wan2.1 / LTX-2.5');

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
            <span className={`w-2 h-2 rounded-full ${isProfileError ? 'bg-amber-400' : 'bg-emerald-400'} inline-block shadow-[0_0_8px_theme(colors.emerald.400)]`}></span> 
            Local Compute Probe Active
          </div>
          <div className="text-xs text-zinc-500 uppercase m-0">Polling /api/compute/local-profile</div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-black p-4 rounded-md border border-zinc-800">
            <div className="text-xs text-zinc-500 uppercase mb-1">Detected VRAM</div>
            <div className="text-xl font-semibold font-mono">
              {profile?.total_vram_gb ? `${profile.total_vram_gb.toFixed(1)} GB` : '-- GB'}
            </div>
          </div>
          <div className="bg-black p-4 rounded-md border border-zinc-800">
            <div className="text-xs text-zinc-500 uppercase mb-1">Active GPU</div>
            <div className="text-xl font-semibold font-mono truncate">
              {profile?.device_name || (profile?.device ? profile.device : 'Local Host')}
            </div>
          </div>
          <div className="bg-black p-4 rounded-md border border-zinc-800">
            <div className="text-xs text-zinc-500 uppercase mb-1">Recommended Engine</div>
            <div className="text-xl font-semibold font-mono text-emerald-400 truncate">
              {recommendedEngine}
            </div>
          </div>
        </div>
      </div>

      <section id="quickstart" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">1. Quickstart</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">Zero-configuration local setup. We rely on Doppler for secrets management. Bypass the $0.30 SaaS markup and run your first $0.00 local inference in under 60 seconds.</p>
        
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden my-6">
          <div className="flex bg-zinc-950 border-b border-zinc-800 p-0">
            <button className="bg-zinc-900 text-zinc-50 font-medium border-none px-4 py-3 text-sm cursor-pointer border-r border-zinc-800 border-b-transparent -mb-[1px]">Terminal</button>
            <button 
              onClick={() => {
                navigator.clipboard.writeText('npm i -g @spacepilot/cli\ndoppler setup -p spacepilot -c dev_personal\ndoppler run -- spacepilot daemon start --port 8088');
                alert('Copied to clipboard!');
              }}
              className="ml-auto bg-transparent border-none text-zinc-400 hover:text-zinc-50 px-4 py-3 cursor-pointer text-sm transition-colors"
            >
              Copy
            </button>
          </div>
          <pre className="p-4 overflow-x-auto font-mono text-sm text-zinc-50"><code className="language-bash">
{`# Install CLI and pull config
npm i -g @spacepilot/cli
doppler setup -p spacepilot -c dev_personal

# Run local hardware diagnostics and start daemon
doppler run -- spacepilot daemon start --port 8088`}
          </code></pre>
        </div>
      </section>

      <section id="architecture" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">2. Platform Architecture</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">SpacePilot utilizes a 4-Layer Composable Stack connecting your local editor via FastMCP to either a local Metal/CUDA runtime or a dynamically provisioned Spot Cloud instance based on the Headroom formula.</p>
        <p className="text-zinc-400 mb-5 leading-relaxed"><strong>Headroom Formula:</strong> <code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">H = VRAM_Total - (OS_Reserve + Model_Weights + KV_Cache + KV_Grad)</code></p>
      </section>

      <section id="models" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">3. Model Zoo & DiT Engines</h2>
        <p className="text-zinc-400 mb-5 leading-relaxed">Our tensor compilation targets the optimal precision for each underlying DiT architecture. Below is the engine capability matrix.</p>
      </section>

      <section id="fastmcp" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">4. Agentic FastMCP Reference</h2>
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
      "engine": { "type": "string", "enum": ["ltx-2.5", "wan-2.1", "hunyuan"] },
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
    return f"Job queued for {engine} at {aspect_ratio}"`}
              </code>
            )}
          </pre>
        </div>
      </section>

      <section id="rest-api" className="mb-10">
        <h2 className="text-[1.75rem] font-semibold tracking-tight border-b border-zinc-800 pb-2 mb-4 mt-10">5. REST API Matrix</h2>
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
                <td className="p-3 text-left border-b border-zinc-800">Returns host hardware constraints and VRAM.</td>
              </tr>
              <tr>
                <td className="p-3 text-left border-b border-zinc-800"><code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">/api/generate/multi-engine</code></td>
                <td className="p-3 text-left border-b border-zinc-800">POST</td>
                <td className="p-3 text-left border-b border-zinc-800">Dispatches multi-engine DiT generation job.</td>
              </tr>
              <tr>
                <td className="p-3 text-left border-b border-zinc-800"><code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">/api/jobs/:id</code></td>
                <td className="p-3 text-left border-b border-zinc-800">GET</td>
                <td className="p-3 text-left border-b border-zinc-800">Polls job status and take URLs.</td>
              </tr>
              <tr>
                <td className="p-3 text-left border-b border-zinc-800"><code className="bg-zinc-900 px-1.5 py-0.5 rounded font-mono text-[0.875em] text-zinc-200">/api/audio/synthesize-local</code></td>
                <td className="p-3 text-left border-b border-zinc-800">POST</td>
                <td className="p-3 text-left border-b border-zinc-800">Kokoro in-process audio synthesis with -16 LUFS.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      
      <div className="h-24"></div>
    </main>
  );
}
