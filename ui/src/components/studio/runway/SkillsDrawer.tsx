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
    accentText: 'text-ink-700',
    accentBg: 'group-hover:bg-strong',
    accentBorder: 'group-hover:border-line-400',
    icon: Type
  },
  {
    id: 'i2v',
    command: '/I2V',
    title: 'Image to Video',
    description: 'Animate first/last frame keyframes',
    accentText: 'text-verify',
    accentBg: 'group-hover:bg-verify-soft',
    accentBorder: 'group-hover:border-verify/30',
    icon: ImageIcon
  },
  {
    id: 'upscale',
    command: '/Upscale',
    title: '4K Super Res',
    description: 'RealESRGAN 4K enhancement',
    accentText: 'text-ink-700',
    accentBg: 'group-hover:bg-strong',
    accentBorder: 'group-hover:border-line-400',
    icon: Scaling
  },
  {
    id: 'loop',
    command: '/Loop',
    title: 'Seamless Loop',
    description: 'Perfect periodic boundary motion',
    accentText: 'text-ink-700',
    accentBg: 'group-hover:bg-strong',
    accentBorder: 'group-hover:border-line-400',
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
    accentText: 'text-ink-700',
    accentBg: 'group-hover:bg-strong',
    accentBorder: 'group-hover:border-line-400',
    icon: ArrowRightCircle
  },
  {
    id: 'director',
    command: '/Director',
    title: 'AI Director',
    description: 'Multi-scene documentary storyboard',
    accentText: 'text-danger',
    accentBg: 'group-hover:bg-danger-soft',
    accentBorder: 'group-hover:border-danger/30',
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
      <div className="max-w-4xl mx-auto w-full pointer-events-auto bg-surface/90 backdrop-blur-md border border-line-200 rounded-2xl p-3 shadow-lg">
        <div className="flex items-center justify-between mb-2.5 px-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-verify" />
            <span className="text-[11px] font-semibold text-ink-700 tracking-wider uppercase font-mono">
              Agent Skills System
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setPrompt('/T2V Cinematic slow-motion tracking shot of ');
              }}
              className="text-[10px] font-mono text-ink-500 hover:text-ink px-2 py-0.5 rounded bg-inset hover:bg-strong border border-line-200 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <Edit3 className="w-3 h-3 text-ink-700" />
              <span>Write it myself</span>
            </button>
            <button
              onClick={() => {
                addChatMessage({
                  role: 'user',
                  text: 'Generate a 5-scene documentary script about Quantum Entanglement and Diffusion Models.',
                });
              }}
              className="text-[10px] font-mono text-verify hover:text-verify/80 px-2 py-0.5 rounded bg-verify-soft hover:bg-verify-soft border border-verify/30 transition-colors flex items-center gap-1 cursor-pointer font-bold"
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
                className={`group relative flex flex-col h-[76px] bg-raised border rounded-xl p-2.5 transition-all duration-200 text-left overflow-hidden cursor-pointer ${
                  isSelected
                    ? 'border-verify bg-inset'
                    : 'border-line-200 hover:border-line-300'
                } ${skill.accentBg} ${skill.accentBorder}`}
              >
                <div className="flex items-center justify-between mb-auto relative z-10">
                  <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-ground/60 ${skill.accentText}`}>
                    {skill.command}
                  </span>
                  <Icon className={`w-3.5 h-3.5 text-ink-500 group-hover:${skill.accentText} transition-colors`} />
                </div>

                <div className="relative z-10 mt-1">
                  <div className="text-xs font-semibold text-ink-900 truncate group-hover:text-ink">
                    {skill.title}
                  </div>
                  <div className="text-[9px] text-ink-500 line-clamp-1">
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
