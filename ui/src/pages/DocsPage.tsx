import { useState } from 'react';
import { 
  Code2, 
  Volume2, 
  Copy, 
  Check, 
  ExternalLink
} from 'lucide-react';

export default function DocsPage() {
  const [copied, setCopied] = useState<string | null>(null);

  const copyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="min-h-screen bg-black text-[#fafafa] flex flex-col font-sans">
      {/* Header */}
      <header className="h-14 bg-[#09090b] border-b border-white/[0.08] px-6 flex items-center justify-between z-20">
        <div className="flex items-center gap-4">
          <a href="/" className="flex items-center gap-2 text-sm font-extrabold tracking-tight">
            <span>🛸</span>
            <span>SpacePilot Docs</span>
          </a>
          <div className="h-4 w-px bg-white/[0.1]" />
          <span className="font-mono text-xs text-[#10b981] bg-[#10b981]/10 px-2 py-0.5 rounded border border-[#10b981]/30">
            v2.8.0 Obsidian Specification
          </span>
        </div>

        <div className="flex items-center gap-4 font-mono text-xs text-[#a1a1aa]">
          <a href="/studio" className="hover:text-white transition-colors">Studio</a>
          <a href="/cockpit" className="hover:text-white transition-colors">Cockpit</a>
          <a href="https://github.com/motionvector-dev/pluto" target="_blank" rel="noreferrer" className="text-white hover:underline flex items-center gap-1">
            GitHub <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </header>

      {/* Docs Layout */}
      <div className="flex-1 max-w-6xl mx-auto w-full p-8 grid grid-cols-12 gap-8">
        {/* Navigation Sidebar */}
        <aside className="col-span-12 md:col-span-3 flex flex-col gap-6 font-mono text-xs">
          <div className="flex flex-col gap-2">
            <span className="text-[#71717a] font-bold uppercase tracking-wider text-[10px]">Overview</span>
            <a href="#quickstart" className="text-white hover:text-[#10b981] transition-colors py-1">Quickstart & Installation</a>
            <a href="#architecture" className="text-[#a1a1aa] hover:text-white transition-colors py-1">System Topology</a>
            <a href="#fastmcp" className="text-[#a1a1aa] hover:text-white transition-colors py-1">FastMCP Directing Protocol</a>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-[#71717a] font-bold uppercase tracking-wider text-[10px]">Engines</span>
            <a href="#ltx" className="text-[#a1a1aa] hover:text-white transition-colors py-1">LTX-2.5 0.0s Daemon</a>
            <a href="#kokoro" className="text-[#a1a1aa] hover:text-white transition-colors py-1">Kokoro -16 LUFS Audio</a>
            <a href="#flf2v" className="text-[#a1a1aa] hover:text-white transition-colors py-1">FLF2V Dual Keyframes</a>
          </div>
        </aside>

        {/* Content Body */}
        <main className="col-span-12 md:col-span-9 flex flex-col gap-12 font-sans">
          {/* Quickstart Section */}
          <section id="quickstart" className="flex flex-col gap-4">
            <h1 className="text-3xl font-extrabold tracking-tight text-white">
              Quickstart & Installation
            </h1>
            <p className="text-sm text-[#a1a1aa] leading-relaxed">
              SpacePilot ships as both a standalone Python runtime and an autonomous FastMCP tool server.
            </p>

            <div className="bg-[#09090b] border border-white/[0.08] rounded-xl p-4 font-mono text-xs relative">
              <button 
                onClick={() => copyCode('pip install spacepilot && sky launch spacepilot.yaml', 'c1')}
                className="absolute top-3 right-3 p-1.5 bg-[#18181b] hover:bg-[#222226] border border-white/[0.1] rounded text-[#a1a1aa] hover:text-white transition-all cursor-pointer"
              >
                {copied === 'c1' ? <Check className="w-3.5 h-3.5 text-[#10b981]" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
              <pre className="text-[#10b981]">pip install spacepilot</pre>
              <pre className="text-[#38bdf8] mt-1">sky launch spacepilot.yaml</pre>
            </div>
          </section>

          {/* FastMCP Protocol Section */}
          <section id="fastmcp" className="flex flex-col gap-4 border-t border-white/[0.08] pt-8">
            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Code2 className="w-5 h-5 text-[#a855f7]" />
              FastMCP Tool Directing
            </h2>
            <p className="text-sm text-[#a1a1aa] leading-relaxed">
              Configure Claude, Cursor, Antigravity, or custom agent swarms to direct cinema shots autonomously via the Model Context Protocol.
            </p>

            <div className="bg-[#09090b] border border-white/[0.08] rounded-xl p-4 font-mono text-xs relative text-[#38bdf8] overflow-x-auto">
              <pre>{`{
  "name": "spacepilot_direct_scene",
  "arguments": {
    "prompt": "Cyberpunk neon alleyway, volumetric rain, anamorphic reflections",
    "camera_pan": 15.0,
    "camera_zoom": 1.4,
    "voice_preset": "af_bella",
    "music_lufs": -16.0,
    "num_takes": 4
  }
}`}</pre>
            </div>
          </section>

          {/* Kokoro Section */}
          <section id="kokoro" className="flex flex-col gap-4 border-t border-white/[0.08] pt-8">
            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Volume2 className="w-5 h-5 text-[#10b981]" />
              Kokoro-82M Audio Engine & Broadcast Mastering
            </h2>
            <p className="text-sm text-[#a1a1aa] leading-relaxed">
              Every take is automatically mastered using 2-pass EBU R128 loudnorm filters. Background music tracks undergo automated sidechain ducking when voice narration is active.
            </p>
          </section>
        </main>
      </div>
    </div>
  );
}
