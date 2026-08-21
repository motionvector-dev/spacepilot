import { 
  Play, 
  Pause, 
  RotateCcw, 
  Volume2, 
  VolumeX, 
  ZoomIn, 
  ZoomOut,
  Layers,
  Scissors
} from 'lucide-react';
import { useTimelineStore } from '../../stores/timelineStore';

export default function TimelineEditor() {
  const { 
    isPlaying, 
    togglePlay, 
    currentTimeSeconds, 
    durationSeconds, 
    seek, 
    tracks,
    zoomLevel,
    setZoomLevel
  } = useTimelineStore();

  const formatSMPTE = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const frames = Math.floor((seconds % 1) * 24);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}:${String(frames).padStart(2, '0')}:00`;
  };

  return (
    <div className="bg-[#09090b] border-t border-white/[0.08] flex flex-col h-64 select-none font-mono text-xs">
      {/* Transport Control Bar */}
      <div className="h-10 bg-[#111114] border-b border-white/[0.08] px-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button 
            onClick={() => seek(0)}
            className="p-1.5 hover:bg-[#18181b] rounded text-[#a1a1aa] hover:text-white transition-colors cursor-pointer"
            title="Rewind to start"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button 
            onClick={togglePlay}
            className="p-1.5 bg-white text-black hover:bg-[#e4e4e7] rounded transition-all shadow-[0_0_12px_rgba(255,255,255,0.15)] cursor-pointer flex items-center gap-1 font-bold text-[11px]"
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5 fill-black" /> : <Play className="w-3.5 h-3.5 fill-black" />}
            <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
          </button>
          <button 
            className="p-1.5 hover:bg-[#18181b] rounded text-[#a1a1aa] hover:text-white transition-colors cursor-pointer ml-1"
            title="Split Clip (Razor)"
          >
            <Scissors className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* SMPTE Timecode Display */}
        <div className="flex items-center gap-3 bg-black/60 px-3 py-1 rounded border border-white/[0.08]">
          <span className="text-[#10b981] font-bold text-xs">
            {formatSMPTE(currentTimeSeconds)}
          </span>
          <span className="text-[#71717a]">/</span>
          <span className="text-[#71717a] text-xs">
            {formatSMPTE(durationSeconds)}
          </span>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setZoomLevel(Math.max(0.5, zoomLevel - 0.2))}
            className="p-1 hover:bg-[#18181b] rounded text-[#71717a] hover:text-white cursor-pointer"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-[10px] text-[#71717a]">{zoomLevel.toFixed(1)}x</span>
          <button 
            onClick={() => setZoomLevel(Math.min(3.0, zoomLevel + 0.2))}
            className="p-1 hover:bg-[#18181b] rounded text-[#71717a] hover:text-white cursor-pointer"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Tracks Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Track Headers Sidebar */}
        <div className="w-48 bg-[#09090b] border-r border-white/[0.08] flex flex-col divide-y divide-white/[0.06] shrink-0">
          {tracks.map((track) => (
            <div key={track.id} className="h-14 px-3 flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2 truncate">
                <Layers className="w-3 h-3 text-[#71717a] shrink-0" />
                <span className="text-white font-medium truncate">{track.name}</span>
              </div>
              <button className="text-[#71717a] hover:text-white cursor-pointer p-1">
                {track.muted ? <VolumeX className="w-3 h-3 text-[#f43f5e]" /> : <Volume2 className="w-3 h-3" />}
              </button>
            </div>
          ))}
        </div>

        {/* Timeline Tracks Lane */}
        <div className="flex-1 bg-black overflow-x-auto relative flex flex-col divide-y divide-white/[0.06]">
          {/* Ruler */}
          <div className="h-6 bg-[#111114] border-b border-white/[0.08] flex items-center px-2 text-[9px] text-[#71717a] select-none">
            {[0, 1, 2, 3, 4].map((s) => (
              <div key={s} className="flex-1 border-l border-white/[0.1] pl-1">
                00:0{s}:00
              </div>
            ))}
          </div>

          {/* Track 1: Video Clip */}
          <div className="h-14 p-1.5 relative">
            <div className="h-full w-full bg-[#10b981]/20 border border-[#10b981]/50 rounded px-2 flex items-center justify-between text-[10px] text-[#10b981] font-bold">
              <span>Take 1 · 4.0s (96 frames @ 24fps)</span>
              <span>ProRes 422</span>
            </div>
          </div>

          {/* Track 2: Voice Audio Waveform */}
          <div className="h-14 p-1.5 relative">
            <div className="h-full w-full bg-[#a855f7]/20 border border-[#a855f7]/50 rounded px-2 flex items-center justify-between text-[10px] text-[#a855f7] font-bold">
              <span>Kokoro Voice (af_bella · 24kHz)</span>
              <span>-16 LUFS</span>
            </div>
          </div>

          {/* Track 3: BGM Track */}
          <div className="h-14 p-1.5 relative">
            <div className="h-full w-full bg-[#06b6d4]/15 border border-[#06b6d4]/40 rounded px-2 flex items-center justify-between text-[10px] text-[#06b6d4] font-bold">
              <span>Cyberpunk Ambience (Sidechained Ducking)</span>
              <span>Stereo</span>
            </div>
          </div>

          {/* Playhead Indicator */}
          <div 
            className="absolute top-0 bottom-0 w-0.5 bg-[#f43f5e] z-30 pointer-events-none"
            style={{ left: `${(currentTimeSeconds / durationSeconds) * 100}%` }}
          >
            <div className="w-2.5 h-2.5 bg-[#f43f5e] -translate-x-[4px] rotate-45" />
          </div>
        </div>
      </div>
    </div>
  );
}
