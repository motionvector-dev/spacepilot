import { useMutation, useQuery } from '@tanstack/react-query';
import type { 
  GenerateRequest, 
  JobResult, 
  AudioSynthRequest, 
  AudioSynthResponse,
  StoryboardDecomposeRequest,
  StoryboardDecomposeResponse 
} from '../types/api';

async function fetchToken(): Promise<string> {
  try {
    const res = await fetch('/api/token');
    if (res.ok) {
      const data = await res.json();
      return data.token || '';
    }
  } catch {
    // fallback
  }
  return '';
}

export function useGenerateVideo() {
  return useMutation<{ job_id: string; status: string; takes?: any[] }, Error, GenerateRequest>({
    mutationFn: async (req: GenerateRequest) => {
      const token = await fetchToken();
      // Try multi-engine endpoint first, fall back to /api/generate
      let res = await fetch('/api/generate/multi-engine', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify(req),
      });

      if (!res.ok) {
        res = await fetch('/api/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'X-Pluto-Token': token } : {}),
          },
          body: JSON.stringify(req),
        });
      }

      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        throw new Error(`Generation failed (${res.status}): ${errText}`);
      }

      return res.json();
    },
  });
}

export function useJobStatus(jobId: string | null) {
  return useQuery<JobResult>({
    queryKey: ['job-status', jobId],
    queryFn: async () => {
      if (!jobId) throw new Error('No job ID provided');
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) throw new Error('Failed to fetch job status');
      return res.json();
    },
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'completed' || status === 'failed') {
        return false;
      }
      return 1500;
    },
  });
}

export function useEnhancePrompt() {
  return useMutation<{ enhanced_prompt: string }, Error, string>({
    mutationFn: async (prompt: string) => {
      const res = await fetch('/api/enhance-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) throw new Error('Failed to enhance prompt');
      return res.json();
    },
  });
}

export function useSynthesizeAudio() {
  return useMutation<AudioSynthResponse, Error, AudioSynthRequest>({
    mutationFn: async (req: AudioSynthRequest) => {
      const token = await fetchToken();
      let res = await fetch('/api/audio/synthesize-local', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify({
          text: req.text,
          voice: req.voice || 'af_bella',
          speed: req.speed ?? 1.0,
          target_lufs: req.target_lufs ?? -16.0,
          bgm_preset: req.bgm_preset,
        }),
      });

      if (!res.ok) {
        // Fallback to voice endpoint
        res = await fetch('/api/generate/voice', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'X-Pluto-Token': token } : {}),
          },
          body: JSON.stringify({
            text: req.text,
            voice: req.voice || 'af_bella',
            speed: req.speed ?? 1.0,
            backend: 'kokoro',
          }),
        });
      }

      if (!res.ok) throw new Error('Failed to synthesize audio');
      return res.json();
    },
  });
}

export interface ImageUploadResponse {
  image_path: string;
  width?: number;
  height?: number;
  file_path?: string;
  path?: string;
}

export function useUploadImage() {
  return useMutation<ImageUploadResponse, Error, File>({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const token = await fetchToken();

      const res = await fetch('/api/upload-image', {
        method: 'POST',
        headers: token ? { 'X-Pluto-Token': token } : {},
        body: formData,
      });

      if (!res.ok) {
        // Return file name as local reference fallback
        return {
          image_path: file.name,
        };
      }

      return res.json();
    },
  });
}

export function useDecomposeStoryboard() {
  return useMutation<StoryboardDecomposeResponse, Error, StoryboardDecomposeRequest>({
    mutationFn: async (req: StoryboardDecomposeRequest) => {
      const token = await fetchToken();
      const res = await fetch('/api/storyboard/decompose', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify({
          script: req.script,
          target_duration_sec: req.target_duration_sec ?? 60.0,
          scene_count: req.scene_count ?? 6,
          style: req.style ?? 'Cinematic 35mm Hollywood',
        }),
      });

      if (!res.ok) {
        // Fallback local decomposition if offline
        const count = req.scene_count ?? 6;
        const dur = (req.target_duration_sec ?? 60) / count;
        const fallbackScenes = [
          {
            scene_idx: 1,
            title: 'Establishing Scene',
            prompt: `Cinematic wide establishing shot: ${req.script.slice(0, 100)}, 35mm anamorphic lens, golden hour`,
            duration_sec: dur,
            camera_motion: 'Dolly In',
            shot_type: 'Wide',
            lighting: 'Golden Hour',
            character_seed: 482910,
          },
          {
            scene_idx: 2,
            title: 'Subject Focus',
            prompt: `Medium tracking shot of main subject moving dynamically, cinematic depth of field, atmospheric lighting`,
            duration_sec: dur,
            camera_motion: 'Pan Right',
            shot_type: 'Medium',
            lighting: 'High Contrast',
            character_seed: 482910,
          },
          {
            scene_idx: 3,
            title: 'Climactic Action',
            prompt: `Dynamic intense action angle with volumetric atmosphere and detailed motion blur, ultra crisp`,
            duration_sec: dur,
            camera_motion: 'Tilt Up',
            shot_type: 'Close-Up',
            lighting: 'Moody Neon',
            character_seed: 482910,
          },
          {
            scene_idx: 4,
            title: 'Resolution Shot',
            prompt: `Slow pan out revealing the wider panoramic vista at dusk, cinematic masterpiece`,
            duration_sec: dur,
            camera_motion: 'Dolly Out',
            shot_type: 'Panoramic',
            lighting: 'Twilight',
            character_seed: 482910,
          }
        ];

        return {
          scenes: fallbackScenes.slice(0, count),
          total_duration_sec: req.target_duration_sec ?? 60,
          character_seed: 482910,
        };
      }

      return res.json();
    },
  });
}
