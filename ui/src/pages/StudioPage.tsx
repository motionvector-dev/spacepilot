import { useState } from 'react';
import { 
  Terminal, 
  Clapperboard,
  Palette,
  Sparkles,
  Command
} from 'lucide-react';
import { useStudioStore } from '../stores/studioStore';
import { useGpuStore } from '../stores/gpuStore';
import TimelineEditor from '../components/studio/TimelineEditor';
import DirectorView from '../components/studio/DirectorView';
import VibeCanvasView from '../components/studio/VibeCanvasView';
import CommandPalette from '../components/studio/CommandPalette';

export default function StudioPage() {
  const { 
    activeMode,
    setActiveMode,
  } = useStudioStore();

  const { status: gpuStatus } = useGpuStore();
  const [cmdOpen, setCmdOpen] = useState(false);

  return (
    <div className="h-screen bg-black text-[#fafafa] flex flex-col font-sans overflow-hidden">
      {/* Studio Top Control Bar */}
      <header className="h-14 bg-[#09090b] border-b border-white/[0.08] px-6 flex items-center justify-between z-20 shrink-0">
        <div className="flex items-center gap-4">
          <a href="/" className="flex items-center gap-2 text-sm font-extrabold tracking-tight">
            <span>🛸</span>
            <span>SpacePilot Studio</span>
          </a>
          <div className="h-4 w-px bg-white/[0.1]" />

          {/* Mode Switcher Tabs */}
          <div className="flex items-center bg-[#111114] p-1 rounded-lg border border-white/[0.08] font-mono text-xs">
            <button
              onClick={() => setActiveMode('director')}
              className={`px-3 py-1 rounded flex items-center gap-1.5 transition-all cursor-pointer ${
                activeMode === 'director'
                  ? 'bg-[#18181b] text-white font-bold border border-white/[0.1]'
                  : 'text-[#71717a] hover:text-white'
              }`}
            >
              <Clapperboard className="w-3.5 h-3.5 text-[#10b981]" />
              Storyboard Director
            </button>
            <button
              onClick={() => setActiveMode('vibe')}
              className={`px-3 py-1 rounded flex items-center gap-1.5 transition-all cursor-pointer ${
                activeMode === 'vibe'
                  ? 'bg-[#18181b] text-white font-bold border border-white/[0.1]'
                  : 'text-[#71717a] hover:text-white'
              }`}
            >
              <Palette className="w-3.5 h-3.5 text-[#06b6d4]" />
              Vibe & MotionVector
            </button>
          </div>

          <div className="h-4 w-px bg-white/[0.1] hidden md:block" />
          <div className="hidden md:flex items-center gap-2 font-mono text-xs text-[#a1a1aa]">
            <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
            <span>{gpuStatus.instanceType.toUpperCase()} (L40S 48GB) · 0.0s Daemon</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Quick Actions (Cmd+K) Trigger */}
          <button
            onClick={() => setCmdOpen(true)}
            className="hidden sm:flex items-center gap-2 text-xs font-mono bg-[#111114] hover:bg-[#18181b] border border-white/[0.08] px-3 py-1.5 rounded text-[#a1a1aa] hover:text-white transition-all cursor-pointer"
          >
            <Command className="w-3 h-3 text-[#10b981]" />
            <span>Quick Actions</span>
            <kbd className="text-[10px] bg-white/[0.06] px-1 rounded border border-white/[0.08]">⌘K</kbd>
          </button>

          <a
            href="/cockpit"
            className="flex items-center gap-1.5 text-xs font-mono bg-[#18181b] hover:bg-[#222226] border border-white/[0.1] px-3 py-1.5 rounded text-[#a1a1aa] hover:text-white transition-all cursor-pointer"
          >
            <Terminal className="w-3.5 h-3.5 text-[#38bdf8]" />
            Cockpit SSH
          </a>
          <button className="flex items-center gap-1.5 text-xs font-semibold bg-white text-black px-4 py-1.5 rounded hover:bg-[#e4e4e7] transition-all shadow-[0_0_16px_rgba(255,255,255,0.15)] cursor-pointer">
            <Sparkles className="w-3.5 h-3.5" />
            Export 4K Master
          </button>
        </div>
      </header>

      {/* Main Studio Viewport Content */}
      <div className="flex-1 flex overflow-hidden">
        {activeMode === 'director' ? <DirectorView /> : <VibeCanvasView />}
      </div>

      {/* Multi-Track NLE Timeline Editor */}
      <TimelineEditor />

      {/* Command Palette (⌘K) Modal */}
      <CommandPalette isOpen={cmdOpen} onClose={() => setCmdOpen(false)} />
    </div>
  );
}
