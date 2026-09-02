import React from 'react';
import { 
  Type, 
  Image as ImageIcon, 
  Scaling, 
  Repeat, 
  Palette, 
  ArrowRightCircle, 
  Clapperboard, 
  Sparkles,
  Wand2,
  Edit3
} from 'lucide-react';
import { useStudioStore } from '../../../stores/studioStore';

interface Skill {
  id: string;
  command: string;
  title: string;
  description: string;
  accentText: string;
  accentBg: string;
  accentBorder: string;
  icon: React.ElementType;
}

const SKILLS: Skill[] = [
  { 
    id: 't2v', 
    command: '/T2V', 
    title: 'Text to Video', 
    description: 'Generate 4K video from text prompt', 
    accentText: 'text-cyan-400',
    accentBg: 'group-hover:bg-cyan-500/10',
    accentBorder: 'group-hover:border-cyan-500/30',
    icon: Type 
  },
  { 
    id: 'i2v', 
    command: '/I2V', 
    title: 'Image to Video', 
    description: 'Animate first/last frame keyframes', 
    accentText: 'text-emerald-400',
    accentBg: 'group-hover:bg-emerald-500/10',
    accentBorder: 'group-hover:border-emerald-500/30',
    icon: ImageIcon 
  },
  { 
    id: 'upscale', 
    command: '/Upscale', 
    title: '4K Super Res', 
    description: 'RealESRGAN 4K enhancement', 
    accentText: 'text-purple-400',
    accentBg: 'group-hover:bg-purple-500/10',
    accentBorder: 'group-hover:border-purple-500/30',
    icon: Scaling 
  },
  { 
    id: 'loop', 
    command: '/Loop', 
    title: 'Seamless Loop', 
    description: 'Perfect periodic boundary motion', 
    accentText: 'text-amber-400',
    accentBg: 'group-hover:bg-amber-500/10',
    accentBorder: 'group-hover:border-amber-500/30',
    icon: Repeat 
  },
  { 
    id: 'style', 
    command: '/Style', 
    title: 'Style Transfer', 
    description: 'Apply aesthetic LoRA styles', 
    accentText: 'text-pink-400',
    accentBg: 'group-hover:bg-pink-500/10',
    accentBorder: 'group-hover:border-pink-500/30',
    icon: Palette 
  },
  { 
    id: 'extend', 
    command: '/Extend', 
    title: 'Video Extend', 
    description: 'Autoregressive temporal expansion', 
    accentText: 'text-blue-400',
    accentBg: 'group-hover:bg-blue-500/10',
    accentBorder: 'group-hover:border-blue-500/30',
    icon: ArrowRightCircle 
  },
  { 
    id: 'director', 
    command: '/Director', 
    title: 'AI Director', 
    description: 'Multi-scene documentary storyboard', 
    accentText: 'text-red-400',
    accentBg: 'group-hover:bg-red-500/10',
    accentBorder: 'group-hover:border-red-500/30',
    icon: Clapperboard 
  },
];

export const SkillsDrawer: React.FC = () => {
  const { 
    activeSkill, 
    setActiveSkill, 
    prompt, 
    setPrompt,
    setStudioExperience,
    addChatMessage
  } = useStudioStore();

  const handleSkillSelect = (skill: Skill) => {
    setActiveSkill(skill.id);
    
    if (skill.id === 'director') {
      setStudioExperience('nle');
      return;
    }

    // Insert or replace skill command in prompt
    let cleanPrompt = prompt;
    SKILLS.forEach((s) => {
      cleanPrompt = cleanPrompt.replace(new RegExp(`^${s.command}\\s*`, 'i'), '');
    });

    setPrompt(`${skill.command} ${cleanPrompt}`.trim());
    addChatMessage({
      role: 'user',
      text: `Activated skill: ${skill.command} (${skill.title})`,
    });
  };

  return (
    <div className="fixed bottom-3 left-[56px] right-[320px] px-6 z-20 pointer-events-none select-none">
      <div className="max-w-4xl mx-auto w-full pointer-events-auto bg-[#09090b]/90 backdrop-blur-md border border-white/10 rounded-2xl p-3 shadow-2xl">
        <div className="flex items-center justify-between mb-2.5 px-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[11px] font-semibold text-white/70 tracking-wider uppercase font-mono">
              Agent Skills System
            </span>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setPrompt('/T2V Cinematic slow-motion tracking shot of ');
              }}
              className="text-[10px] font-mono text-white/50 hover:text-white px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <Edit3 className="w-3 h-3 text-cyan-400" />
              <span>Write it myself</span>
            </button>
            <button
              onClick={() => {
                addChatMessage({
                  role: 'user',
                  text: 'Generate a 5-scene documentary script about Quantum Entanglement and Diffusion Models.',
                });
              }}
              className="text-[10px] font-mono text-emerald-400 hover:text-emerald-300 px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 transition-colors flex items-center gap-1 cursor-pointer font-bold"
            >
              <Wand2 className="w-3 h-3" />
              <span>Create with Agent</span>
            </button>
          </div>
        </div>
        
        {/* Skills Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
          {SKILLS.map((skill) => {
            const Icon = skill.icon;
            const isSelected = activeSkill === skill.id;

            return (
              <button
                key={skill.id}
                onClick={() => handleSkillSelect(skill)}
                className={`group relative flex flex-col h-[76px] bg-[#111114] border rounded-xl p-2.5 transition-all duration-200 text-left overflow-hidden cursor-pointer ${
                  isSelected
                    ? 'border-emerald-400 bg-[#18181b] shadow-[0_0_12px_rgba(16,185,129,0.2)]'
                    : 'border-white/10 hover:border-white/20'
                } ${skill.accentBg} ${skill.accentBorder}`}
              >
                <div className="flex items-center justify-between mb-auto relative z-10">
                  <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-black/60 ${skill.accentText}`}>
                    {skill.command}
                  </span>
                  <Icon className={`w-3.5 h-3.5 text-white/40 group-hover:${skill.accentText} transition-colors`} />
                </div>
                
                <div className="relative z-10 mt-1">
                  <div className="text-xs font-semibold text-white/90 truncate group-hover:text-white">
                    {skill.title}
                  </div>
                  <div className="text-[9px] text-white/40 line-clamp-1">
                    {skill.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default SkillsDrawer;
