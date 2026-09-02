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
      let consecutiveFailures = 0;
      let skipUntilAttempt = 0;
      const MAX_CONSECUTIVE_FAILURES = 6;

      const interval = setInterval(async () => {
        attempts++;
        if (attempts < skipUntilAttempt) return; // backing off after a run of failed status checks

        try {
          const status = await api.getJobStatus(jobId);
          consecutiveFailures = 0;
          setProgress((prev) => Math.min(prev + 12, 92));

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
          // A poll failure (network blip, proxy 502, GPU mid-restart) is not a completion —
          // the job is still queued as far as we know. Back off and keep polling; only
          // surface an error once failures are persistent, never flip to success.
          consecutiveFailures++;
          if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            clearInterval(interval);
            setIsGenerating(false);
            setError(
              `Lost contact with the render job after ${consecutiveFailures} failed status checks: ${
                pollErr instanceof Error ? pollErr.message : 'unknown error'
              }`
            );
            return;
          }
          skipUntilAttempt = attempts + Math.min(2 ** consecutiveFailures, 16);
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
