import { useState, useRef, useEffect, useCallback } from 'react';
import { useSynthesizeAudio } from '../../hooks/useGenerate';
import {
  Mic,
  Loader2,
  Play,
  Pause,
  Volume2,
  Check,
  Music,
  Radio
} from 'lucide-react';

interface AudioVoiceStepProps {
  dialogue?: string;
  setDialogue?: (d: string) => void;
  voice?: string;
  setVoice?: (v: string) => void;
  bgmBed?: string;
  setBgmBed?: (b: string) => void;
  ducking?: boolean;
  setDucking?: (d: boolean) => void;
}

export function AudioVoiceStep({
  dialogue: propDialogue,
  setDialogue: propSetDialogue,
  voice: propVoice,
  setVoice: propSetVoice,
  bgmBed: propBgmBed,
  setBgmBed: propSetBgmBed,
  ducking: propDucking,
  setDucking: propSetDucking,
}: AudioVoiceStepProps = {}) {
  const [internalDialogue, setInternalDialogue] = useState('');
  const [internalVoice, setInternalVoice] = useState('af_heart');
  const [internalBgm, setInternalBgm] = useState('ambient-cinematic');
  const [internalDucking, setInternalDucking] = useState(true);

  const dialogue = propDialogue !== undefined ? propDialogue : internalDialogue;
  const setDialogue = propSetDialogue || setInternalDialogue;
  const voice = propVoice !== undefined ? propVoice : internalVoice;
  const setVoice = propSetVoice || setInternalVoice;
  const bgmBed = propBgmBed !== undefined ? propBgmBed : internalBgm;
  const setBgmBed = propSetBgmBed || setInternalBgm;
  const ducking = propDucking !== undefined ? propDucking : internalDucking;
  const setDucking = propSetDucking || setInternalDucking;

  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackTime, setPlaybackTime] = useState('0:00');
  const [durationText, setDurationText] = useState('0:00');

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);

  const synthMutation = useSynthesizeAudio();

  const handleSynthesize = async () => {
    if (!dialogue.trim()) return;
    try {
      const res = await synthMutation.mutateAsync({
        text: dialogue,
        voice,
        target_lufs: ducking ? -16.0 : undefined,
        bgm_preset: bgmBed !== 'none' ? bgmBed : undefined,
      });

      if (res.audio_url) {
        setAudioUrl(res.audio_url);
        setIsPlaying(false);
      }
    } catch {
      // Handled by synthMutation.isError
    }
  };

  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    if (analyserRef.current && isPlaying) {
      const bufferLength = analyserRef.current.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyserRef.current.getByteFrequencyData(dataArray);

      const barWidth = (width / bufferLength) * 2.5;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * height * 0.85;

        // Dynamic gradient for waveform bars — neutral luminance ramp, no hue.
        const gradient = ctx.createLinearGradient(0, height, 0, height - barHeight);
        gradient.addColorStop(0, '#71717a');
        gradient.addColorStop(1, '#fafafa');

        ctx.fillStyle = gradient;
        ctx.fillRect(x, height - barHeight, barWidth - 1, barHeight);

        x += barWidth + 1;
      }
    } else {
      // Oscillating smooth dynamic idle/preview waveform bars
      const numBars = 48;
      const barWidth = width / numBars;
      const time = Date.now() * 0.003;

      for (let i = 0; i < numBars; i++) {
        const factor = Math.sin(time + i * 0.3) * 0.5 + 0.5;
        const baseHeight = isPlaying ? 10 + factor * (height - 16) : 4 + Math.sin(i * 0.2) * 8 + 6;

        ctx.fillStyle = isPlaying ? 'rgba(250, 250, 250, 0.55)' : 'rgba(161, 161, 170, 0.25)';
        const x = i * barWidth + 1;
        const y = (height - baseHeight) / 2;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth - 2, baseHeight, 2);
        ctx.fill();
      }
    }

    animationFrameRef.current = requestAnimationFrame(drawWaveform);
  }, [isPlaying]);

  useEffect(() => {
    animationFrameRef.current = requestAnimationFrame(drawWaveform);
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [drawWaveform]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      // Initialize Web Audio Context if not already done
      if (!audioCtxRef.current) {
        try {
          const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          audioCtxRef.current = new AudioContextClass();
          analyserRef.current = audioCtxRef.current.createAnalyser();
          analyserRef.current.fftSize = 64;
          sourceRef.current = audioCtxRef.current.createMediaElementSource(audioRef.current);
          sourceRef.current.connect(analyserRef.current);
          analyserRef.current.connect(audioCtxRef.current.destination);
        } catch {
          // Web Audio setup fallback
        }
      }

      if (audioCtxRef.current?.state === 'suspended') {
        audioCtxRef.current.resume();
      }

      audioRef.current.play()
        .then(() => setIsPlaying(true))
        .catch(() => setIsPlaying(false));
    }
  };

  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    const cur = audioRef.current.currentTime;
    const dur = audioRef.current.duration || 0;
    const curM = Math.floor(cur / 60);
    const curS = Math.floor(cur % 60).toString().padStart(2, '0');
    setPlaybackTime(`${curM}:${curS}`);

    if (dur > 0) {
      const durM = Math.floor(dur / 60);
      const durS = Math.floor(dur % 60).toString().padStart(2, '0');
      setDurationText(`${durM}:${durS}`);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setPlaybackTime('0:00');
  };

  return (
    <div className="flex flex-col gap-4 p-5 bg-surface border border-line-200 rounded-xl hover:border-line-300 transition-colors">
      <div className="flex justify-between items-center border-b border-line-100 pb-3">
        <div className="flex items-center gap-2">
          <Mic className="w-4 h-4 text-ink-700" />
          <h2 className="text-[13px] font-semibold text-ink-700 uppercase tracking-wider">
            Voiceover &amp; BGM Ducking
          </h2>
        </div>
        <div className="flex items-center gap-2.5">
          <span className="text-[11px] font-mono text-verify bg-verify-soft px-2 py-0.5 rounded border border-verify/20">
            -16 LUFS (EBU R128)
          </span>
          <button
            type="button"
            onClick={() => setDucking(!ducking)}
            className={`w-8 h-4 rounded-full p-0.5 transition-colors focus:outline-none cursor-pointer ${
              ducking ? 'bg-verify' : 'bg-strong'
            }`}
            title="Auto-duck BGM under voiceover"
          >
            <div className={`w-3 h-3 rounded-full bg-ink transition-transform ${
              ducking ? 'translate-x-4' : 'translate-x-0'
            }`} />
          </button>
        </div>
      </div>

      {/* Voiceover Script Input */}
      <div className="flex flex-col gap-1.5">
        <label className="text-[11px] font-bold text-ink-500 uppercase tracking-wider">
          Dialogue / Narration Script
        </label>
        <textarea
          value={dialogue}
          onChange={(e) => setDialogue(e.target.value)}
          rows={2}
          className="w-full p-3 bg-ground border border-line-300 rounded-lg text-[13px] text-ink focus:outline-none focus:border-line-500 placeholder-ink-300 font-sans"
          placeholder="Optional narrator / dialogue speech (Kokoro TTS auto-ducked over BGM track)..."
        />
      </div>

      {/* Controls Grid: Voice Profile & BGM Bed */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-semibold text-ink-700 flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-agent" />
            <span>Kokoro Voice Profile</span>
          </label>
          <select
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
            className="w-full bg-ground border border-line-300 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-line-500 cursor-pointer"
          >
            <option value="af_heart">Heart (Warm Female · Recommended)</option>
            <option value="af_bella">Bella (Expressive Female)</option>
            <option value="af_alloy">Alloy (Clear Female)</option>
            <option value="am_michael">Michael (Narrator Male)</option>
            <option value="am_fenrir">Fenrir (Deep Male)</option>
            <option value="am_echo">Echo (Authoritative Male)</option>
            <option value="am_adam">Adam (Cinematic Male)</option>
            <option value="bf_alice">Alice (British Female)</option>
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-semibold text-ink-700 flex items-center gap-1.5">
            <Music className="w-3.5 h-3.5 text-ink-700" />
            <span>Background Music (BGM Bed)</span>
          </label>
          <select
            value={bgmBed}
            onChange={(e) => setBgmBed(e.target.value)}
            className="w-full bg-ground border border-line-300 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-line-500 cursor-pointer"
          >
            <option value="ambient-cinematic">Ambient Pad (Cinematic Float)</option>
            <option value="synth-pop-electronic">Sci-Fi Pulse (Electronic Beat)</option>
            <option value="deep-house-chill">Deep Chill (Lo-Fi Atmospheric)</option>
            <option value="synthwave">Retro Synthwave 80s</option>
            <option value="none">No BGM (Dry Voice Track)</option>
          </select>
        </div>
      </div>

      {/* Dynamic Audio Waveform Visualizer Canvas */}
      <div className="flex flex-col gap-2 p-3.5 bg-inset border border-line-200 rounded-xl">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-ink-500" />
            <span className="text-[11px] font-mono text-ink-700">Waveform Spectral Canvas</span>
          </div>
          {audioUrl && (
            <span className="text-[11px] font-mono text-ink-700">
              {playbackTime} / {durationText}
            </span>
          )}
        </div>

        {/* Real Canvas Waveform */}
        <canvas
          ref={canvasRef}
          width={440}
          height={48}
          className="w-full h-12 rounded-lg bg-ground border border-line-100"
        />

        <div className="flex items-center justify-between pt-1 gap-2">
          <button
            type="button"
            onClick={handleSynthesize}
            disabled={synthMutation.isPending || !dialogue.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-inset hover:bg-strong border border-line-300 rounded-lg text-xs font-semibold text-ink-900 hover:text-ink transition-all cursor-pointer disabled:opacity-50"
          >
            {synthMutation.isPending ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-agent" />
                <span>Synthesizing &amp; Ducking...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 text-ink-700" />
                <span>Preview Ducked VO</span>
              </>
            )}
          </button>

          {audioUrl && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={togglePlay}
                className="p-1.5 rounded-lg bg-inset hover:bg-strong text-ink transition-all cursor-pointer"
                title={isPlaying ? 'Pause Preview' : 'Play Preview'}
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-ink" />}
              </button>
              <div className="flex items-center gap-1 text-[11px] font-mono text-verify bg-verify-soft px-2 py-1 rounded border border-verify/20">
                <Check className="w-3 h-3 text-verify" />
                <span>Ready</span>
              </div>
            </div>
          )}
        </div>

        {audioUrl && (
          <audio
            ref={audioRef}
            src={audioUrl}
            onTimeUpdate={handleTimeUpdate}
            onEnded={handleEnded}
            className="hidden"
          />
        )}
      </div>
    </div>
  );
}
