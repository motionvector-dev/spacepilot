import { create } from 'zustand';

export interface Take {
  id: number;
  seed: number;
  videoUrl?: string;
  // The backend job_id this take is polling — distinct from `id`, which is
  // only a local 1..N slot index for the take grid.
  jobId?: string;
  error?: string;
  panDeg: number;
  zoomRatio: number;
  selected: boolean;
  status: 'idle' | 'generating' | 'ready' | 'error';
}

export interface StoryboardScene {
  id: string;
  prompt: string;
  duration: number;
  panDeg: number;
  zoomRatio: number;
  status: 'idle' | 'generating' | 'ready';
  videoUrl?: string;
}

export interface AttachedMedia {
  name: string;
  url: string;
  file?: File;
}

export interface GenerationPreferences {
  mode: 'ask' | 'auto';
  target: 'quality' | 'speed' | 'cost' | 'custom';
  engine: string;
  duration: number;
  aspectRatio: string;
  enhance: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  text: string;
  reasoning?: string;
  tags?: string[];
  timestamp: string;
}

interface StudioState {
  // Dual Studio Mode Switcher: 'runway' (Runway Gen-4 Agent Mode) vs 'nle' (Pro NLE Storyboard Mode)
  studioExperience: 'runway' | 'nle';
  setStudioExperience: (experience: 'runway' | 'nle') => void;

  // NLE Sub-mode: 'director' (AI Director Storyboard) vs 'vibe' (Vibe Canvas & MotionVector)
  activeMode: 'director' | 'vibe';
  setActiveMode: (mode: 'director' | 'vibe') => void;

  // Prompt & Skills
  prompt: string;
  setPrompt: (p: string) => void;
  activeSkill: string;
  setActiveSkill: (skill: string) => void;
  attachedImage: AttachedMedia | null;
  setAttachedImage: (img: AttachedMedia | null) => void;

  // Generation Preferences
  generationPreferences: GenerationPreferences;
  setGenerationPreferences: (prefs: Partial<GenerationPreferences>) => void;

  // Conversational Agent Chat
  chatMessages: ChatMessage[];
  addChatMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void;

  // Model & Motion Parameters
  motionAmount: number;
  setMotionAmount: (v: number) => void;
  guidanceScale: number;
  setGuidanceScale: (v: number) => void;
  voicePreset: string;
  setVoicePreset: (v: string) => void;
  musicLufs: number;
  setMusicLufs: (l: number) => void;
  panAngle: number;
  setPanAngle: (a: number) => void;
  zoomRatio: number;
  setZoomRatio: (z: number) => void;

  // Takes & Scenes
  selectedTakeId: number;
  setSelectedTakeId: (id: number) => void;
  takes: Take[];
  setTakes: (takes: Take[]) => void;
  updateTake: (id: number, patch: Partial<Take>) => void;
  clearTakes: () => void;
  scenes: StoryboardScene[];
  activeSceneId: string;
  setActiveSceneId: (id: string) => void;
  addScene: (prompt: string) => void;
  removeScene: (id: string) => void;
  updateScenePrompt: (id: string, prompt: string) => void;
  updateScene: (id: string, patch: Partial<StoryboardScene>) => void;

  // Generation & Audio Status
  isGenerating: boolean;
  setIsGenerating: (g: boolean) => void;
  lastGeneratedJobId: string | null;
  setLastGeneratedJobId: (id: string | null) => void;
  audioWaveformPlaying: boolean;
  setAudioWaveformPlaying: (p: boolean) => void;
}

export const useStudioStore = create<StudioState>((set) => ({
  studioExperience: 'runway',
  setStudioExperience: (studioExperience) => set({ studioExperience }),

  activeMode: 'director',
  setActiveMode: (activeMode) => set({ activeMode }),

  prompt: 'Cyberpunk neon alleyway, volumetric rain, anamorphic reflections, 4k photorealistic',
  setPrompt: (prompt) => set({ prompt }),
  activeSkill: 't2v',
  setActiveSkill: (activeSkill) => set({ activeSkill }),
  attachedImage: null,
  setAttachedImage: (attachedImage) => set({ attachedImage }),

  generationPreferences: {
    mode: 'ask',
    target: 'quality',
    engine: 'ltx-2.5',
    duration: 4,
    aspectRatio: '16:9',
    enhance: true,
  },
  setGenerationPreferences: (prefs) =>
    set((state) => ({
      generationPreferences: { ...state.generationPreferences, ...prefs },
    })),

  chatMessages: [
    {
      id: 'msg-1',
      role: 'user',
      text: 'I want a slow pan across a futuristic neon city, raining heavily.',
      timestamp: '10:42 AM',
    },
    {
      id: 'msg-2',
      role: 'agent',
      text: "I've configured the scene for a classic cyberpunk atmosphere. Let's adjust the camera guidance and motion parameters for optimal photorealism.",
      reasoning: `> Analyzed prompt: "slow pan", "neon city", "raining"\n> Added structural keywords: "cinematic lighting", "8k resolution", "anamorphic reflections"\n> Camera motion set to: Pan Right (+15°)\n> Style alignment: Cyberpunk / Sci-Fi / Photorealistic`,
      tags: ['slow pan right', 'futuristic neon city', 'heavy rain', 'cinematic lighting', '8k resolution'],
      timestamp: '10:42 AM',
    },
  ],
  addChatMessage: (msg) =>
    set((state) => ({
      chatMessages: [
        ...state.chatMessages,
        {
          ...msg,
          id: `msg-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ],
    })),

  motionAmount: 60,
  setMotionAmount: (motionAmount) => set({ motionAmount }),
  guidanceScale: 7.5,
  setGuidanceScale: (guidanceScale) => set({ guidanceScale }),

  voicePreset: 'af_bella',
  setVoicePreset: (voicePreset) => set({ voicePreset }),
  musicLufs: -16.0,
  setMusicLufs: (musicLufs) => set({ musicLufs }),
  panAngle: 15,
  setPanAngle: (panAngle) => set({ panAngle }),
  zoomRatio: 1.4,
  setZoomRatio: (zoomRatio) => set({ zoomRatio }),

  selectedTakeId: 1,
  setSelectedTakeId: (selectedTakeId) => set({ selectedTakeId }),
  isGenerating: false,
  setIsGenerating: (isGenerating) => set({ isGenerating }),
  lastGeneratedJobId: null,
  setLastGeneratedJobId: (lastGeneratedJobId) => set({ lastGeneratedJobId }),
  audioWaveformPlaying: false,
  setAudioWaveformPlaying: (audioWaveformPlaying) => set({ audioWaveformPlaying }),

  // Empty until a real generation completes — no placeholder takes. A "ready"
  // take that never rendered anything is the fabricated-success shape this was
  // built to remove.
  takes: [],
  setTakes: (takes) => set({ takes }),
  updateTake: (id, patch) =>
    set((state) => ({
      takes: state.takes.map((t) => (t.id === id ? { ...t, ...patch } : t)),
    })),
  clearTakes: () => set({ takes: [] }),

  activeSceneId: '',
  setActiveSceneId: (activeSceneId) => set({ activeSceneId }),
  scenes: [],
  addScene: (prompt) =>
    set((state) => {
      const newId = `scene-${Date.now()}`;
      return {
        scenes: [
          ...state.scenes,
          { id: newId, prompt, duration: 4.0, panDeg: 0, zoomRatio: 1.0, status: 'idle' }
        ],
        activeSceneId: newId,
      };
    }),
  removeScene: (id) =>
    set((state) => {
      const scenes = state.scenes.filter((s) => s.id !== id);
      return {
        scenes,
        activeSceneId: state.activeSceneId === id ? (scenes[0]?.id || '') : state.activeSceneId,
      };
    }),
  updateScenePrompt: (id, prompt) =>
    set((state) => ({
      scenes: state.scenes.map((s) => (s.id === id ? { ...s, prompt } : s)),
    })),
  updateScene: (id, patch) =>
    set((state) => ({
      scenes: state.scenes.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    })),
}));
