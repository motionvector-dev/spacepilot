import { useState, useEffect } from 'react';
import { 
  Search, 
  Sparkles, 
  Film, 
  Terminal, 
  Layers, 
  Maximize2
} from 'lucide-react';
import { useStudioStore } from '../../stores/studioStore';

interface CommandItem {
  id: string;
  title: string;
  sub: string;
  icon: any;
  action: () => void;
  shortcut?: string;
}

export default function CommandPalette({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const { setActiveMode } = useStudioStore();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const commands: CommandItem[] = [
    {
      id: 'director-mode',
      title: 'Switch to Storyboard Director Mode',
      sub: 'Multi-scene narrative filmstrip reel',
      icon: Film,
      action: () => {
        setActiveMode('director');
        onClose();
      }
    },
    {
      id: 'vibe-mode',
      title: 'Switch to Vibe Canvas & MotionVector',
      sub: 'Live KaTeX vector overlay & single-shot plate generator',
      icon: Layers,
      action: () => {
        setActiveMode('vibe');
        onClose();
      }
    },
    {
      id: 'export-4k',
      title: 'Export 4K Master (P0 Composite Order)',
      sub: 'Upscale plate to 3840×2160 UHD, then render Vello vectors',
      icon: Sparkles,
      action: () => {
        alert('Dispatched 4K Master Vello Composite job.');
        onClose();
      },
      shortcut: '⌘E'
    },
    {
      id: 'cockpit-ssh',
      title: 'Open Web SSH Cockpit',
      sub: 'PTY terminal bridge & real-time GPU hardware diagnostics',
      icon: Terminal,
      action: () => {
        window.location.href = '/cockpit';
      }
    },
    {
      id: 'fullscreen',
      title: 'Toggle Fullscreen Mode',
      sub: 'Maximize studio workspace to display resolution',
      icon: Maximize2,
      action: () => {
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen();
        } else {
          document.exitFullscreen();
        }
        onClose();
      },
      shortcut: 'F'
    }
  ];

  const filtered = commands.filter(
    (c) =>
      c.title.toLowerCase().includes(query.toLowerCase()) ||
      c.sub.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div 
      onClick={onClose}
      className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-start justify-center pt-24 p-4 font-sans"
    >
      <div 
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl bg-[#09090b] border border-white/[0.15] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 border-b border-white/[0.08]">
          <Search className="w-4 h-4 text-[#71717a] shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search studio actions..."
            autoFocus
            className="w-full bg-transparent px-3 py-4 text-xs font-sans text-white focus:outline-none placeholder-[#71717a]"
          />
          <kbd className="font-mono text-[10px] text-[#71717a] bg-white/[0.06] px-1.5 py-0.5 rounded border border-white/[0.08]">
            ESC
          </kbd>
        </div>

        {/* Command Results */}
        <div className="p-2 flex flex-col gap-1 max-h-80 overflow-y-auto font-sans">
          {filtered.map((c) => {
            const Icon = c.icon;
            return (
              <div
                key={c.id}
                onClick={c.action}
                className="flex items-center justify-between p-3 rounded-xl hover:bg-white/[0.06] cursor-pointer transition-all group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#111114] border border-white/[0.08] text-[#10b981] group-hover:border-[#10b981]/40">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs font-bold text-white group-hover:text-[#10b981] transition-colors">
                      {c.title}
                    </span>
                    <span className="text-[10px] text-[#71717a] font-mono">{c.sub}</span>
                  </div>
                </div>

                {c.shortcut && (
                  <kbd className="font-mono text-[10px] text-[#a1a1aa] bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.08]">
                    {c.shortcut}
                  </kbd>
                )}
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="text-center py-8 text-xs font-mono text-[#71717a]">
              No commands matching "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
