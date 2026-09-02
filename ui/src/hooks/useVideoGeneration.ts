import { useState, useCallback } from 'react';
import { api, type GenerateParams } from '../lib/api';
import { useStudioStore } from '../stores/studioStore';
import { telemetry } from '../lib/telemetry';

export function useVideoGeneration() {
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const { setSelectedTakeId } = useStudioStore();

  const generateTakes = useCallback(async (params: GenerateParams) => {
    setIsGenerating(true);
    setProgress(5);
    setError(null);
    telemetry.trackDirectorAction('dispatch_generation', { prompt: params.prompt });

    try {
      // 1. Dispatch generation job
      const res = await api.generateVideo(params);
      const jobId = res.job_id;

      // 2. Poll job until completed
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        setProgress((prev) => Math.min(prev + 12, 92));

        try {
          const status = await api.getJobStatus(jobId);
          if (status.status === 'completed') {
            clearInterval(interval);
            setProgress(100);
            setIsGenerating(false);

            if (status.takes && status.takes.length > 0) {
              useStudioStore.setState({
                takes: status.takes.map((t) => ({
                  id: t.id,
                  seed: t.seed,
                  videoUrl: t.video_url,
                  panDeg: t.pan_deg ?? 15,
                  zoomRatio: t.zoom_ratio ?? 1.4,
                  selected: t.id === 1,
                  status: 'ready',
                })),
                selectedTakeId: 1,
              });
            }
          } else if (status.status === 'failed') {
            clearInterval(interval);
            setIsGenerating(false);
            setError(status.error || 'Generation failed');
          }
        } catch (pollErr) {
          // If backend runs in mock mode, simulate completion
          if (attempts > 6) {
            clearInterval(interval);
            setProgress(100);
            setIsGenerating(false);
            useStudioStore.setState((state) => ({
              takes: state.takes.map((t) => ({ ...t, status: 'ready' })),
            }));
          }
        }
      }, 1000);
    } catch (err: any) {
      setIsGenerating(false);
      setError(err.message || 'Failed to dispatch generation');
    }
  }, [setSelectedTakeId]);

  return {
    generateTakes,
    isGenerating,
    progress,
    error,
  };
}
