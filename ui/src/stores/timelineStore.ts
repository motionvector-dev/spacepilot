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
  shuttleRate: number; // 0 = stop, 1 = normal, 2, 4, 8 = forward, -2, -4, -8 = rewind
  inPoint: number | null;
  outPoint: number | null;
  togglePlay: () => void;
  seek: (seconds: number) => void;
  setZoomLevel: (z: number) => void;
  stepFrames: (deltaFrames: number) => void;
  stepTime: (deltaSeconds: number) => void;
  shuttleStop: () => void;
  shuttleForward: () => void;
  shuttleReverse: () => void;
  setInPoint: (pos?: number) => void;
  setOutPoint: (pos?: number) => void;
  clearInOutPoints: () => void;
}

export const useTimelineStore = create<TimelineState>((set, get) => ({
  isPlaying: false,
  setIsPlaying: (isPlaying) => set({ isPlaying, shuttleRate: isPlaying ? 1 : 0 }),
  currentTimeSeconds: 0,
  setCurrentTime: (currentTimeSeconds) => set({ currentTimeSeconds }),
  durationSeconds: 4.0,
  setDuration: (durationSeconds) => set({ durationSeconds }),
  fps: 24,
  zoomLevel: 1.0,
  shuttleRate: 0,
  inPoint: null,
  outPoint: null,
  tracks: [
    { id: 't1', type: 'video', name: 'Video 1 (LTX-2.5 48GB)', muted: false, solo: false, volume: 1.0 },
    { id: 't2', type: 'voice', name: 'Voice (Kokoro af_bella)', muted: false, solo: false, volume: 1.0 },
    { id: 't3', type: 'music', name: 'BGM (Sidechained -16 LUFS)', muted: false, solo: false, volume: 0.8 },
  ],
  togglePlay: () => {
    const { isPlaying, shuttleRate } = get();
    if (isPlaying || shuttleRate !== 0) {
      set({ isPlaying: false, shuttleRate: 0 });
    } else {
      set({ isPlaying: true, shuttleRate: 1 });
    }
  },
  seek: (currentTimeSeconds) => {
    const { durationSeconds } = get();
    set({ currentTimeSeconds: Math.max(0, Math.min(durationSeconds, currentTimeSeconds)) });
  },
  setZoomLevel: (zoomLevel) => set({ zoomLevel: Math.max(0.5, Math.min(3.0, zoomLevel)) }),
  stepFrames: (deltaFrames) => {
    const { currentTimeSeconds, fps, durationSeconds } = get();
    const deltaSec = deltaFrames / fps;
    set({
      isPlaying: false,
      shuttleRate: 0,
      currentTimeSeconds: Math.max(0, Math.min(durationSeconds, currentTimeSeconds + deltaSec)),
    });
  },
  stepTime: (deltaSeconds) => {
    const { currentTimeSeconds, durationSeconds } = get();
    set({
      isPlaying: false,
      shuttleRate: 0,
      currentTimeSeconds: Math.max(0, Math.min(durationSeconds, currentTimeSeconds + deltaSeconds)),
    });
  },
  shuttleStop: () => {
    set({ isPlaying: false, shuttleRate: 0 });
  },
  shuttleForward: () => {
    const { shuttleRate } = get();
    let nextRate = 2;
    if (shuttleRate === 2) nextRate = 4;
    else if (shuttleRate === 4) nextRate = 8;
    else if (shuttleRate === 8) nextRate = 2;
    else if (shuttleRate <= 0) nextRate = 2;

    set({ isPlaying: true, shuttleRate: nextRate });
  },
  shuttleReverse: () => {
    const { shuttleRate } = get();
    let nextRate = -2;
    if (shuttleRate === -2) nextRate = -4;
    else if (shuttleRate === -4) nextRate = -8;
    else if (shuttleRate === -8) nextRate = -2;
    else if (shuttleRate >= 0) nextRate = -2;

    set({ isPlaying: true, shuttleRate: nextRate });
  },
  setInPoint: (pos) => {
    const { currentTimeSeconds } = get();
    set({ inPoint: pos ?? currentTimeSeconds });
  },
  setOutPoint: (pos) => {
    const { currentTimeSeconds } = get();
    set({ outPoint: pos ?? currentTimeSeconds });
  },
  clearInOutPoints: () => {
    set({ inPoint: null, outPoint: null });
  },
}));
