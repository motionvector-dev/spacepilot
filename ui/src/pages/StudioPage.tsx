import { useState, useEffect } from 'react';
import { 
  Terminal, 
  Clapperboard, 
  Palette, 
  Sparkles, 
  Command, 
  Loader2, 
  Bot, 
  Layers
} from 'lucide-react';
import { useStudioStore } from '../stores/studioStore';
import { useTimelineStore } from '../stores/timelineStore';
import { useGpuStore } from '../stores/gpuStore';
import { formatVram, gpuDotClass, gpuLabel } from '../lib/gpuFormat';
import { useGpuPoller } from '../hooks/useGpuPoller';

// Runway Gen-4 Agent Components
import { 
  LeftSidebarRail, 
  TopMiniHeader, 
  CenterStagePromptHero, 
  SkillsDrawer, 
  AgentRightPanel 
} from '../components/studio/runway';

// Pro NLE Components
import TimelineEditor from '../components/studio/TimelineEditor';
import DirectorView from '../components/studio/DirectorView';
import VibeCanvasView from '../components/studio/VibeCanvasView';
import CommandPalette from '../components/studio/CommandPalette';
import ExportDrawer from '../components/studio/ExportDrawer';

export default function StudioPage() {
  const { 
    studioExperience,
    setStudioExperience,
    activeMode,
    setActiveMode,
    isGenerating
  } = useStudioStore();

  const {
    isPlaying,
    shuttleRate,
    togglePlay,
    shuttleStop,
    shuttleReverse,
    shuttleForward,
    stepFrames,
    stepTime,
    setInPoint,
    setOutPoint,
    clearInOutPoints,
  } = useTimelineStore();

  const { status: gpuStatus, statusError: gpuStatusError } = useGpuStore();
  const [cmdOpen, setCmdOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  // Activate continuous background telemetry polling
  useGpuPoller(4000);

  // ── Global NLE Transport & Navigation Keyboard Shortcuts Engine ──
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement;
      const isTyping =
        activeEl instanceof HTMLInputElement ||
        activeEl instanceof HTMLTextAreaElement ||
        activeEl?.getAttribute('contenteditable') === 'true';

      // Global Modal / Command Shortcuts
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCmdOpen((prev) => !prev);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'e') {
        e.preventDefault();
        setExportOpen((prev) => !prev);
        return;
      }
      if (e.key === 'Escape') {
        setCmdOpen(false);
        setExportOpen(false);
        return;
      }

      // Do not intercept transport shortcuts while typing in inputs
      if (isTyping) return;

      // NLE Transport Shortcuts (J / K / L Shuttle + Space + Frame Stepping)
      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      } else if (e.key.toLowerCase() === 'k') {
        e.preventDefault();
        shuttleStop();
      } else if (e.key.toLowerCase() === 'j') {
        e.preventDefault();
        shuttleReverse();
      } else if (e.key.toLowerCase() === 'l') {
        e.preventDefault();
        shuttleForward();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (e.shiftKey) {
          stepTime(-1.0);
        } else {
          stepFrames(-1);
        }
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (e.shiftKey) {
          stepTime(1.0);
        } else {
          stepFrames(1);
        }
      } else if (e.key.toLowerCase() === 'i') {
        e.preventDefault();
        setInPoint();
      } else if (e.key.toLowerCase() === 'o') {
        e.preventDefault();
        setOutPoint();
      } else if ((e.altKey || e.metaKey) && e.key.toLowerCase() === 'x') {
        e.preventDefault();
        clearInOutPoints();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlay, shuttleStop, shuttleReverse, shuttleForward, stepFrames, stepTime, setInPoint, setOutPoint, clearInOutPoints]);

  // ── High-Precision Realtime Playback / Shuttle Ticker ──
  useEffect(() => {
    if (!isPlaying && shuttleRate === 0) return;

    let lastTimestamp = performance.now();
    let frameId: number;

    const tick = (now: number) => {
      const dt = (now - lastTimestamp) / 1000;
      lastTimestamp = now;

      const rate = shuttleRate !== 0 ? shuttleRate : (isPlaying ? 1 : 0);
      if (rate !== 0) {
        const state = useTimelineStore.getState();
        let nextTime = state.currentTimeSeconds + dt * rate;

        if (rate > 0 && nextTime >= state.durationSeconds) {
          // Loop playback smoothly
          nextTime = 0;
        } else if (rate < 0 && nextTime <= 0) {
          // Rewind reached beginning
          nextTime = 0;
          useTimelineStore.getState().shuttleStop();
        }

        useTimelineStore.getState().setCurrentTime(Math.max(0, Math.min(state.durationSeconds, nextTime)));
      }

      frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [isPlaying, shuttleRate]);

  return (
    <div className="h-screen bg-ground text-ink flex overflow-hidden font-sans select-none">
      {/* Persistent Left Sidebar Navigation Rail */}
      <LeftSidebarRail />

      {/* ── Mode 1: Runway Gen-4 Agent Creative Experience ── */}
      {studioExperience === 'runway' ? (
        <div className="flex-1 flex flex-col pl-[56px] relative h-full overflow-hidden">
          {/* Minimal 44px Top Header */}
          <TopMiniHeader 
            onOpenCmdPalette={() => setCmdOpen(true)}
            onOpenExportDrawer={() => setExportOpen(true)}
          />

          {/* Center Stage Prompt Hero */}
          <CenterStagePromptHero />

          {/* Bottom Skills Drawer */}
          <SkillsDrawer />

          {/* Right Conversational Agent Panel */}
          <AgentRightPanel />
        </div>
      ) : (
        /* ── Mode 2: Pro NLE Multi-Track Storyboard Experience ── */
        <div className="flex-1 flex flex-col pl-[56px] h-full overflow-hidden">
          {/* Pro NLE Top Control Header */}
          <header className="h-12 bg-surface border-b border-line-200 px-4 flex items-center justify-between z-20 shrink-0 select-none">
            <div className="flex items-center gap-3">
              {/* Studio Experience Mode Switcher */}
              <div className="flex items-center bg-raised p-0.5 rounded-lg border border-line-200 font-mono text-xs">
                <button
                  onClick={() => setStudioExperience('runway')}
                  className="px-2.5 py-1 rounded flex items-center gap-1.5 text-ink-700 hover:text-ink transition-all cursor-pointer"
                  title="Switch to Runway Gen-4 Agent Mode"
                >
                  <Bot className="w-3.5 h-3.5 text-verify" />
                  <span>Agent Mode</span>
                </button>
                <button
                  onClick={() => setStudioExperience('nle')}
                  className="px-2.5 py-1 rounded flex items-center gap-1.5 bg-inset text-ink font-bold border border-line-400 transition-all cursor-pointer"
                  title="Currently in Pro NLE Storyboard Mode"
                >
                  <Layers className="w-3.5 h-3.5 text-ink" />
                  <span>Pro NLE Mode</span>
                </button>
              </div>

              <div className="h-4 w-px bg-line-200" />

              {/* NLE View Tabs: Director vs Vibe Canvas */}
              <div className="flex items-center bg-raised p-0.5 rounded-lg border border-line-200 font-mono text-xs">
                <button
                  onClick={() => setActiveMode('director')}
                  className={`px-3 py-1 rounded flex items-center gap-1.5 transition-all cursor-pointer ${
                    activeMode === 'director'
                      ? 'bg-inset text-ink font-bold border border-line-200'
                      : 'text-ink-500 hover:text-ink'
                  }`}
                >
                  <Clapperboard className="w-3.5 h-3.5 text-verify" />
                  Storyboard Director
                </button>
                <button
                  onClick={() => setActiveMode('vibe')}
                  className={`px-3 py-1 rounded flex items-center gap-1.5 transition-all cursor-pointer ${
                    activeMode === 'vibe'
                      ? 'bg-inset text-ink font-bold border border-line-200'
                      : 'text-ink-500 hover:text-ink'
                  }`}
                >
                  <Palette className="w-3.5 h-3.5 text-ink" />
                  Vibe & MotionVector
                </button>
              </div>

              <div className="h-4 w-px bg-line-200 hidden md:block" />
              <div className="hidden md:flex items-center gap-2 font-mono text-xs text-ink-700">
                <span className={`w-2 h-2 rounded-full ${gpuDotClass(gpuStatus, gpuStatusError)}`} />
                <span>
                  {gpuLabel(gpuStatus, gpuStatusError)} · {formatVram(gpuStatus)}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              {/* Quick Actions (Cmd+K) */}
              <button
                onClick={() => setCmdOpen(true)}
                className="hidden sm:flex items-center gap-2 text-xs font-mono bg-raised hover:bg-inset border border-line-200 px-3 py-1.5 rounded-lg text-ink-700 hover:text-ink transition-all cursor-pointer"
                title="Quick Actions (⌘K)"
              >
                <Command className="w-3 h-3 text-verify" />
                <span>Quick Actions</span>
                <kbd className="text-[10px] bg-strong px-1 rounded border border-line-200">⌘K</kbd>
              </button>

              <a
                href="/cockpit"
                className="flex items-center gap-1.5 text-xs font-mono bg-inset hover:bg-strong border border-line-200 px-3 py-1.5 rounded-lg text-ink-700 hover:text-ink transition-all cursor-pointer"
              >
                <Terminal className="w-3.5 h-3.5 text-ink-700" />
                Cockpit SSH
              </a>

              <button 
                disabled={isGenerating}
                onClick={() => setExportOpen(true)}
                className="flex items-center gap-1.5 text-xs font-semibold bg-accent text-accent-contrast px-4 py-1.5 rounded-lg hover:opacity-90 transition-all cursor-pointer disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Generating...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Export 4K Master</span>
                  </>
                )}
              </button>
            </div>
          </header>

          {/* Main NLE Workspace Content */}
          <div className="flex-1 flex overflow-hidden">
            {activeMode === 'director' ? <DirectorView /> : <VibeCanvasView />}
          </div>

          {/* Multi-Track NLE Timeline Editor */}
          <TimelineEditor />
        </div>
      )}

      {/* Command Palette (⌘K) Modal */}
      <CommandPalette isOpen={cmdOpen} onClose={() => setCmdOpen(false)} />

      {/* Export Master Delivery Drawer */}
      <ExportDrawer isOpen={exportOpen} onClose={() => setExportOpen(false)} />
    </div>
  );
}
