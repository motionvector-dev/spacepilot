import { useMutation, useQuery } from '@tanstack/react-query';
import type { GenerateRequest, JobResult, AudioSynthRequest, AudioSynthResponse } from '../types/api';

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
  return useMutation<{ job_id: string; status: string }, Error, GenerateRequest>({
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
      const res = await fetch('/api/audio/synthesize-local', {
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
        }),
      });
      if (!res.ok) throw new Error('Failed to synthesize audio');
      return res.json();
    },
  });
}
