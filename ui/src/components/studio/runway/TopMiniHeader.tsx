import { useState } from 'react';
import { 
  Rocket, 
  MoreHorizontal, 
  Sparkles, 
  Command, 
  Bot, 
  Clapperboard, 
  Terminal, 
  FileText,
  Edit2
} from 'lucide-react';
import { useStudioStore } from '../../../stores/studioStore';
import { formatVram, formatAccruedCost, gpuDotClass, gpuLabel } from '../../../lib/gpuFormat';
import { useGpuStore } from '../../../stores/gpuStore';

interface TopMiniHeaderProps {
  onOpenCmdPalette?: () => void;
  onOpenExportDrawer?: () => void;
}

export const TopMiniHeader = ({
  onOpenCmdPalette,
  onOpenExportDrawer,
}: TopMiniHeaderProps) => {
  const { studioExperience, setStudioExperience } = useStudioStore();
  const { status: gpuStatus, statusError, launchGpu, isLaunching } = useGpuStore();

  const [projectTitle, setProjectTitle] = useState('Diffusion Physics Documentary · Ep 01');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const navigate = (path: string) => {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const estimatedCost = formatAccruedCost(gpuStatus);

  return (
    <header className="fixed top-0 left-[56px] right-0 h-[44px] bg-surface/90 backdrop-blur-md border-b border-line-200 flex items-center justify-between px-4 z-30 select-none">
      {/* Left: Chat/Session Title & Studio Mode Switcher */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2">
          {isEditingTitle ? (
            <input
              type="text"
              value={projectTitle}
              onChange={(e) => setProjectTitle(e.target.value)}
              onBlur={() => setIsEditingTitle(false)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setIsEditingTitle(false);
              }}
              autoFocus
              className="bg-inset border border-line-300 rounded px-2 py-0.5 text-xs text-ink outline-none font-medium max-w-[280px]"
            />
          ) : (
            <button
              onClick={() => setIsEditingTitle(true)}
              className="flex items-center gap-1.5 text-xs font-medium text-ink-900 hover:text-ink group truncate max-w-[320px] text-left cursor-pointer"
              title="Click to rename project"
            >
              <span className="truncate">{projectTitle}</span>
              <Edit2 className="w-3 h-3 text-ink-300 group-hover:text-ink-700 shrink-0" />
            </button>
          )}
          <span className="text-[10px] text-ink-500 px-2 py-0.5 rounded-full bg-inset border border-line-200 font-mono shrink-0">
            Session #829
          </span>
        </div>

        <div className="h-4 w-px bg-line-200 hidden sm:block shrink-0" />

        {/* Dual Studio Mode Switcher Pill */}
        <div className="hidden sm:flex items-center bg-raised p-0.5 rounded-lg border border-line-200 font-mono text-[11px]">
          <button
            onClick={() => setStudioExperience('runway')}
            className={`px-2.5 py-1 rounded flex items-center gap-1.5 transition-all cursor-pointer ${
              studioExperience === 'runway'
                ? 'bg-inset text-verify font-bold border border-verify/30'
                : 'text-ink-500 hover:text-ink'
            }`}
            title="Runway Gen-4 Agent Creative Mode"
          >
            <Bot className="w-3.5 h-3.5" />
            <span>Agent Mode</span>
          </button>
          <button
            onClick={() => setStudioExperience('nle')}
            className={`px-2.5 py-1 rounded flex items-center gap-1.5 transition-all cursor-pointer ${
              studioExperience === 'nle'
                ? 'bg-strong text-ink-900 font-bold border border-line-400'
                : 'text-ink-500 hover:text-ink'
            }`}
            title="Professional NLE Multi-Track Storyboard Mode"
          >
            <Clapperboard className="w-3.5 h-3.5" />
            <span>Pro NLE Mode</span>
          </button>
        </div>
      </div>

      {/* Right: GPU Telemetry & Actions */}
      <div className="flex items-center gap-2.5 shrink-0">
        {/* GPU Telemetry Capsule */}
        <div
          onClick={() => navigate('/cockpit')}
          className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-inset hover:bg-strong border border-line-200 text-ink-700 text-xs font-mono transition-all cursor-pointer"
          title="Click to view Cockpit GPU Metrics"
        >
          <span className={`w-2 h-2 rounded-full ${gpuDotClass(gpuStatus, statusError)}`} />
          <span className="text-ink-700 hidden md:inline">{gpuLabel(gpuStatus, statusError)} ·</span>
          <span className={`font-semibold ${gpuStatus.vramUsedGb === null ? 'text-ink-500' : 'text-verify'}`}>{formatVram(gpuStatus)}</span>
          <span className="text-ink-500">·</span>
          <span className="text-ink-900 font-medium">{estimatedCost}</span>
        </div>

        {/* Command Palette Trigger (⌘K) */}
        <button
          onClick={onOpenCmdPalette}
          className="hidden md:flex items-center gap-1.5 h-7 px-2.5 rounded-md bg-inset hover:bg-strong border border-line-200 text-xs text-ink-700 hover:text-ink transition-colors cursor-pointer font-mono"
          title="Open Command Palette (⌘K)"
        >
          <Command className="w-3 h-3 text-verify" />
          <span>⌘K</span>
        </button>

        {/* Launch GPU Button */}
        <button
          onClick={() => launchGpu()}
          disabled={isLaunching}
          className="h-7 px-3 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer bg-accent text-accent-contrast hover:brightness-110"
          title="Start AWS L40S Spot GPU Instance"
        >
          <Rocket className={`w-3.5 h-3.5 ${isLaunching ? 'animate-bounce' : ''}`} />
          <span>{isLaunching ? 'Starting...' : 'Launch GPU'}</span>
        </button>

        {/* Export Master Button */}
        <button
          onClick={onOpenExportDrawer}
          className="h-7 px-3 rounded-md bg-inset hover:bg-strong border border-line-300 text-ink text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer"
          title="Export 4K Master Documentary"
        >
          <Sparkles className="w-3.5 h-3.5 text-ink-700" />
          <span className="hidden sm:inline">Export</span>
        </button>

        <div className="w-px h-4 bg-line-200 mx-0.5" />

        {/* More Actions Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="w-7 h-7 flex items-center justify-center rounded hover:bg-inset text-ink-700 hover:text-ink transition-colors cursor-pointer"
            title="More Options"
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>

          {showMenu && (
            <div
              className="absolute right-0 mt-2 w-48 bg-raised border border-line-200 rounded-xl shadow-lg py-1 z-50 text-xs font-sans"
              onMouseLeave={() => setShowMenu(false)}
            >
              <button
                onClick={() => {
                  setShowMenu(false);
                  onOpenCmdPalette?.();
                }}
                className="w-full px-3 py-2 text-left text-ink-700 hover:text-ink hover:bg-inset flex items-center gap-2 cursor-pointer"
              >
                <Command className="w-3.5 h-3.5 text-verify" />
                <span>Command Palette (⌘K)</span>
              </button>
              <button
                onClick={() => {
                  setShowMenu(false);
                  onOpenExportDrawer?.();
                }}
                className="w-full px-3 py-2 text-left text-ink-700 hover:text-ink hover:bg-inset flex items-center gap-2 cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5 text-ink-700" />
                <span>Export Master (⌘E)</span>
              </button>
              <div className="h-px bg-line-100 my-1" />
              <button
                onClick={() => {
                  setShowMenu(false);
                  navigate('/cockpit');
                }}
                className="w-full px-3 py-2 text-left text-ink-700 hover:text-ink hover:bg-inset flex items-center gap-2 cursor-pointer"
              >
                <Terminal className="w-3.5 h-3.5 text-ink-700" />
                <span>Cockpit Terminal</span>
              </button>
              <button
                onClick={() => {
                  setShowMenu(false);
                  navigate('/docs');
                }}
                className="w-full px-3 py-2 text-left text-ink-700 hover:text-ink hover:bg-inset flex items-center gap-2 cursor-pointer"
              >
                <FileText className="w-3.5 h-3.5 text-ink-500" />
                <span>Documentation</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default TopMiniHeader;
