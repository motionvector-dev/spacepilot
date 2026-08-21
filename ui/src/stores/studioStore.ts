import { create } from 'zustand';

export interface Take {
  id: number;
  seed: number;
  videoUrl?: string;
  panDeg: number;
  zoomRatio: number;
  selected: boolean;
  status: 'idle' | 'generating' | 'ready' | 'error';
}

interface StudioState {
  prompt: string;
  setPrompt: (p: string) => void;
  voicePreset: string;
  setVoicePreset: (v: string) => void;
  musicLufs: number;
  setMusicLufs: (l: number) => void;
  panAngle: number;
  setPanAngle: (a: number) => void;
  zoomRatio: number;
  setZoomRatio: (z: number) => void;
  selectedTakeId: number;
  setSelectedTakeId: (id: number) => void;
  takes: Take[];
  isGenerating: boolean;
  setIsGenerating: (g: boolean) => void;
  audioWaveformPlaying: boolean;
  setAudioWaveformPlaying: (p: boolean) => void;
}

export const useStudioStore = create<StudioState>((set) => ({
  prompt: 'Cyberpunk neon alleyway, volumetric rain, anamorphic reflections, 4k photorealistic',
  setPrompt: (prompt) => set({ prompt }),
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
  audioWaveformPlaying: false,
  setAudioWaveformPlaying: (audioWaveformPlaying) => set({ audioWaveformPlaying }),
  takes: [
    { id: 1, seed: 42801, panDeg: 15, zoomRatio: 1.4, selected: true, status: 'ready' },
    { id: 2, seed: 42802, panDeg: 15, zoomRatio: 1.4, selected: false, status: 'ready' },
    { id: 3, seed: 42803, panDeg: 15, zoomRatio: 1.4, selected: false, status: 'ready' },
    { id: 4, seed: 42804, panDeg: 15, zoomRatio: 1.4, selected: false, status: 'ready' },
  ],
}));
