import React, { useState } from 'react';
import { 
  Home, 
  Bot, 
  Clapperboard, 
  PlusCircle, 
  LayoutDashboard, 
  Flame, 
  FileText, 
  History, 
  Folder, 
  Settings, 
  Sparkles,
  SlidersHorizontal,
  ChevronRight,
  Layers
} from 'lucide-react';
import { useStudioStore } from '../../../stores/studioStore';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path?: string;
  action?: () => void;
  badge?: string;
}

export const LeftSidebarRail: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const { studioExperience, setStudioExperience, setPrompt } = useStudioStore();

  const navigate = (path: string) => {
    if (window.location.pathname === path) return;
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const navItems: NavItem[] = [
    {
      id: 'home',
      label: 'Home',
      icon: <Home className="w-5 h-5" />,
      path: '/',
      action: () => navigate('/'),
    },
    {
      id: 'agent',
      label: 'Runway Agent Mode',
      icon: <Bot className="w-5 h-5 text-emerald-400" />,
      action: () => {
        setStudioExperience('runway');
        if (window.location.pathname !== '/studio') navigate('/studio');
      },
      badge: 'Gen-4',
    },
    {
      id: 'nle',
      label: 'Pro NLE Storyboard',
      icon: <Clapperboard className="w-5 h-5 text-cyan-400" />,
      action: () => {
        setStudioExperience('nle');
        if (window.location.pathname !== '/studio') navigate('/studio');
      },
      badge: 'NLE',
    },
    {
      id: 'create',
      label: 'Create Studio',
      icon: <PlusCircle className="w-5 h-5 text-blue-400" />,
      path: '/create',
      action: () => navigate('/create'),
    },
    {
      id: 'cockpit',
      label: 'Cockpit Telemetry',
      icon: <LayoutDashboard className="w-5 h-5 text-sky-400" />,
      path: '/cockpit',
      action: () => navigate('/cockpit'),
    },
    {
      id: 'oven',
      label: 'Swarm Oven',
      icon: <Flame className="w-5 h-5 text-amber-400" />,
      path: '/admin/oven',
      action: () => navigate('/admin/oven'),
    },
    {
      id: 'docs',
      label: 'Documentation',
      icon: <FileText className="w-5 h-5 text-zinc-400" />,
      path: '/docs',
      action: () => navigate('/docs'),
    },
    {
      id: 'recents',
      label: 'Recents',
      icon: <History className="w-5 h-5 text-purple-400" />,
      action: () => {
        setPrompt('Visualizing Transformer Attention Matrices & Residual Streams');
        if (window.location.pathname !== '/studio') navigate('/studio');
      },
    },
    {
      id: 'assets',
      label: 'Media Bin',
      icon: <Folder className="w-5 h-5 text-indigo-400" />,
      action: () => {
        setStudioExperience('nle');
        if (window.location.pathname !== '/studio') navigate('/studio');
      },
    },
  ];

  const effectiveExpanded = isPinned || isExpanded;

  return (
    <nav
      className={`fixed left-0 top-0 bottom-0 z-40 flex flex-col bg-[#09090b] border-r border-white/10 transition-all duration-300 select-none ${
        effectiveExpanded ? 'w-[240px] shadow-2xl' : 'w-[56px]'
      }`}
      onMouseEnter={() => !isPinned && setIsExpanded(true)}
      onMouseLeave={() => !isPinned && setIsExpanded(false)}
      aria-label="Pluto Studio Navigation"
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-[44px] px-3 shrink-0 border-b border-white/5 bg-black/40">
        <a 
          href="/" 
          onClick={(e) => { e.preventDefault(); navigate('/'); }}
          className="flex items-center gap-3 overflow-hidden text-decoration-none"
        >
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500/20 via-cyan-500/20 to-blue-500/20 border border-white/10 flex items-center justify-center shrink-0 shadow-inner">
            <span className="text-white font-extrabold text-sm tracking-tighter">MV</span>
          </div>
          {effectiveExpanded && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-xs text-white tracking-wide truncate font-sans">
                MOTION<span className="text-emerald-400">VECTOR</span>
              </span>
              <span className="text-[9px] font-mono text-white/40 tracking-wider">PLUTO 2.5 PRO</span>
            </div>
          )}
        </a>

        {effectiveExpanded && (
          <button
            onClick={() => setIsPinned(!isPinned)}
            className={`p-1 rounded text-white/40 hover:text-white transition-colors cursor-pointer text-xs ${
              isPinned ? 'text-emerald-400 bg-emerald-500/10' : ''
            }`}
            title={isPinned ? 'Unpin Sidebar' : 'Pin Sidebar'}
          >
            <ChevronRight className={`w-3.5 h-3.5 transition-transform ${isPinned ? 'rotate-180' : ''}`} />
          </button>
        )}
      </div>

      {/* New Session Quick Action */}
      <div className="p-2 border-b border-white/5">
        <button
          onClick={() => {
            setPrompt('');
            setStudioExperience('runway');
            if (window.location.pathname !== '/studio') navigate('/studio');
          }}
          className={`flex items-center w-full h-9 px-2 rounded-lg bg-white/5 hover:bg-emerald-500/10 border border-white/10 hover:border-emerald-500/30 text-white/90 hover:text-emerald-400 transition-all cursor-pointer group ${
            !effectiveExpanded ? 'justify-center' : 'gap-2.5'
          }`}
          title="Start New Generation Session"
        >
          <Sparkles className="w-4 h-4 text-emerald-400 shrink-0 group-hover:scale-110 transition-transform" />
          {effectiveExpanded && (
            <span className="text-xs font-semibold truncate">New Session</span>
          )}
        </button>
      </div>

      {/* Main Navigation Links */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-1 scrollbar-hide">
        {navItems.map((item) => {
          const isCurrentActive =
            (item.id === 'agent' && studioExperience === 'runway' && window.location.pathname === '/studio') ||
            (item.id === 'nle' && studioExperience === 'nle' && window.location.pathname === '/studio') ||
            (item.path && window.location.pathname === item.path);

          return (
            <button
              key={item.id}
              onClick={item.action}
              className={`flex items-center w-full h-9 px-2 rounded-lg transition-all text-xs font-medium cursor-pointer group relative ${
                isCurrentActive
                  ? 'bg-[#18181b] text-white border border-white/15 shadow-sm font-semibold'
                  : 'text-white/60 hover:text-white hover:bg-white/5 border border-transparent'
              } ${!effectiveExpanded ? 'justify-center' : 'justify-between'}`}
              title={!effectiveExpanded ? item.label : undefined}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="flex items-center justify-center w-5 h-5 shrink-0">
                  {item.icon}
                </div>
                {effectiveExpanded && (
                  <span className="truncate">{item.label}</span>
                )}
              </div>

              {effectiveExpanded && item.badge && (
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-white/10 text-white/80 border border-white/10">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom Dual Studio Mode Switcher & Profile Footer */}
      <div className="p-2 border-t border-white/10 mt-auto bg-black/60 space-y-2">
        {/* Studio Mode Quick Toggle Pill */}
        <div className="bg-[#111114] border border-white/10 rounded-lg p-1">
          {effectiveExpanded ? (
            <div className="grid grid-cols-2 gap-1 text-[10px] font-mono">
              <button
                onClick={() => setStudioExperience('runway')}
                className={`py-1 px-1.5 rounded text-center transition-all cursor-pointer flex items-center justify-center gap-1 ${
                  studioExperience === 'runway'
                    ? 'bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30'
                    : 'text-white/50 hover:text-white'
                }`}
              >
                <Bot className="w-3 h-3" />
                <span>Agent</span>
              </button>
              <button
                onClick={() => setStudioExperience('nle')}
                className={`py-1 px-1.5 rounded text-center transition-all cursor-pointer flex items-center justify-center gap-1 ${
                  studioExperience === 'nle'
                    ? 'bg-cyan-500/20 text-cyan-400 font-bold border border-cyan-500/30'
                    : 'text-white/50 hover:text-white'
                }`}
              >
                <Layers className="w-3 h-3" />
                <span>NLE</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => setStudioExperience(studioExperience === 'runway' ? 'nle' : 'runway')}
              className="w-full flex items-center justify-center p-1 rounded hover:bg-white/5 text-emerald-400 transition-colors"
              title={`Switch to ${studioExperience === 'runway' ? 'Pro NLE Storyboard Mode' : 'Runway Gen-4 Agent Mode'}`}
            >
              <SlidersHorizontal className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* User Account / Settings Pill */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/cockpit')}
            className={`flex items-center w-full h-9 px-1.5 rounded-lg hover:bg-white/5 transition-colors text-white/70 hover:text-white cursor-pointer ${
              !effectiveExpanded ? 'justify-center' : 'gap-2'
            }`}
            title="Saurabh · Pro 4K Tier"
          >
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-purple-500 to-indigo-500 flex items-center justify-center text-[10px] font-bold text-white shrink-0 border border-white/20">
              S
            </div>
            {effectiveExpanded && (
              <div className="flex flex-col text-left min-w-0 flex-1">
                <span className="text-xs font-semibold text-white truncate">Saurabh</span>
                <span className="text-[9px] font-mono text-emerald-400 truncate">PRO 4K TIER</span>
              </div>
            )}
            {effectiveExpanded && (
              <Settings className="w-3.5 h-3.5 text-white/40 hover:text-white" />
            )}
          </button>
        </div>
      </div>
    </nav>
  );
};

export default LeftSidebarRail;
