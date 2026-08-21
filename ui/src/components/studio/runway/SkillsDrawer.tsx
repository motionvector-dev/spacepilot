import React from 'react';

interface Skill {
  id: string;
  command: string;
  title: string;
  description: string;
  accent: string;
  icon: string;
}

const SKILLS: Skill[] = [
  { id: 't2v', command: '/T2V', title: 'Text to Video', description: 'Generate video from text prompt', accent: 'group-hover:text-cyan-400', icon: 'i-lucide-type' },
  { id: 'i2v', command: '/I2V', title: 'Image to Video', description: 'Animate first/last frame', accent: 'group-hover:text-emerald-400', icon: 'i-lucide-image' },
  { id: 'upscale', command: '/Upscale', title: 'Upscale', description: 'Enhance resolution & detail', accent: 'group-hover:text-purple-400', icon: 'i-lucide-scaling' },
  { id: 'loop', command: '/Loop', title: 'Loop Video', description: 'Create seamless looping videos', accent: 'group-hover:text-amber-400', icon: 'i-lucide-repeat' },
  { id: 'style', command: '/Style', title: 'Style Transfer', description: 'Apply visual styles to video', accent: 'group-hover:text-pink-400', icon: 'i-lucide-palette' },
  { id: 'extend', command: '/Extend', title: 'Extend', description: 'Generate continuation of video', accent: 'group-hover:text-blue-400', icon: 'i-lucide-arrow-right-circle' },
  { id: 'director', command: '/Director', title: 'Director Mode', description: 'Multi-camera & advanced control', accent: 'group-hover:text-red-400', icon: 'i-lucide-clapperboard' },
];

export const SkillsDrawer: React.FC = () => {
  return (
    <div className="absolute bottom-8 left-[56px] right-[320px] px-8 z-20 pointer-events-none">
      <div className="max-w-5xl mx-auto w-full pointer-events-auto">
        <div className="flex items-center gap-2 mb-4 px-2">
          <span className="w-4 h-4 i-lucide-sparkles text-white/40" />
          <h3 className="text-xs font-semibold text-white/50 tracking-wider uppercase font-geist">
            Available Skills
          </h3>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {SKILLS.map((skill) => (
            <button
              key={skill.id}
              className="group relative flex flex-col h-[100px] bg-[#18181b] border border-white/5 rounded-xl p-3 hover:bg-[#222226] hover:border-white/10 transition-all duration-300 text-left overflow-hidden shadow-sm hover:shadow-md"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              
              <div className="flex items-center justify-between mb-auto relative z-10">
                <span className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-black/40 text-white/70 transition-colors ${skill.accent}`}>
                  {skill.command}
                </span>
                <span className={`w-4 h-4 text-white/30 transition-colors ${skill.accent} ${skill.icon}`} />
              </div>
              
              <div className="relative z-10">
                <div className="text-sm font-semibold text-white/90 truncate">
                  {skill.title}
                </div>
                <div className="text-[10px] text-white/40 line-clamp-1 mt-0.5 font-geist">
                  {skill.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
