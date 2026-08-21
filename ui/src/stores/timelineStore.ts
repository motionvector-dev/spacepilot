import { create } from 'zustand';

export interface TimelineTrack {
  id: string;
  type: 'video' | 'voice' | 'music';
  name: string;
  muted: boolean;
  solo: boolean;
  volume: number;
}

interface TimelineState {
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
  currentTimeSeconds: number;
  setCurrentTime: (seconds: number) => void;
  durationSeconds: number;
  setDuration: (duration: number) => void;
  fps: number;
  zoomLevel: number;
  tracks: TimelineTrack[];
  togglePlay: () => void;
  seek: (seconds: number) => void;
  setZoomLevel: (z: number) => void;
}

export const useTimelineStore = create<TimelineState>((set) => ({
  isPlaying: false,
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  currentTimeSeconds: 0,
  setCurrentTime: (currentTimeSeconds) => set({ currentTimeSeconds }),
  durationSeconds: 4.0,
  setDuration: (durationSeconds) => set({ durationSeconds }),
  fps: 24,
  zoomLevel: 1.0,
  tracks: [
    { id: 't1', type: 'video', name: 'Video 1 (LTX-2.5 48GB)', muted: false, solo: false, volume: 1.0 },
    { id: 't2', type: 'voice', name: 'Voice (Kokoro af_bella)', muted: false, solo: false, volume: 1.0 },
    { id: 't3', type: 'music', name: 'BGM (Sidechained -16 LUFS)', muted: false, solo: false, volume: 0.8 },
  ],
  togglePlay: () => set((s) => ({ isPlaying: !s.isPlaying })),
  seek: (currentTimeSeconds) => set({ currentTimeSeconds }),
  setZoomLevel: (zoomLevel) => set({ zoomLevel }),
}));
