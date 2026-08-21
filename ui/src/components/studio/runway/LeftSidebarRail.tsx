import React, { useState } from 'react';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'home', label: 'Home', icon: <span className="w-5 h-5 i-lucide-home" /> },
  { id: 'agent', label: 'Agent Director', icon: <span className="w-5 h-5 i-lucide-bot" /> },
  { id: 'create', label: 'Create', icon: <span className="w-5 h-5 i-lucide-plus-circle" /> },
  { id: 'cockpit', label: 'Cockpit', icon: <span className="w-5 h-5 i-lucide-layout-dashboard" /> },
  { id: 'oven', label: 'Oven', icon: <span className="w-5 h-5 i-lucide-flame" /> },
  { id: 'docs', label: 'Docs', icon: <span className="w-5 h-5 i-lucide-file-text" /> },
  { id: 'recents', label: 'Recents', icon: <span className="w-5 h-5 i-lucide-history" /> },
  { id: 'assets', label: 'Assets', icon: <span className="w-5 h-5 i-lucide-folder" /> },
];

export const LeftSidebarRail: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <nav
      className={`fixed left-0 top-0 bottom-0 z-40 flex flex-col bg-[#09090b] border-r border-white/10 transition-all duration-300 ${
        isExpanded ? 'w-[240px]' : 'w-[56px]'
      }`}
      onMouseEnter={() => setIsExpanded(true)}
      onMouseLeave={() => setIsExpanded(false)}
    >
      <div className="flex items-center h-[44px] px-3 shrink-0 border-b border-white/5">
        <div className="w-8 h-8 rounded bg-white/5 flex items-center justify-center shrink-0">
          <span className="text-white font-bold text-lg i-lucide-triangle" />
        </div>
        {isExpanded && (
          <span className="ml-3 font-semibold text-sm text-white/90 whitespace-nowrap">
            MotionVector
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto py-4 px-2 space-y-1 scrollbar-hide">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className="flex items-center w-full h-10 px-2 rounded-md hover:bg-white/5 transition-colors text-white/60 hover:text-white group"
            title={!isExpanded ? item.label : undefined}
          >
            <div className="flex items-center justify-center w-6 h-6 shrink-0">
              {item.icon}
            </div>
            {isExpanded && (
              <span className="ml-3 text-sm font-medium whitespace-nowrap">
                {item.label}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="p-2 border-t border-white/10 mt-auto">
        <button
          className="flex items-center w-full h-10 px-2 rounded-md hover:bg-white/5 transition-colors text-white/60 hover:text-white"
        >
          <div className="flex items-center justify-center w-6 h-6 shrink-0">
            <span className="w-5 h-5 i-lucide-settings" />
          </div>
          {isExpanded && (
            <span className="ml-3 text-sm font-medium whitespace-nowrap">
              Settings
            </span>
          )}
        </button>
      </div>
    </nav>
  );
};
