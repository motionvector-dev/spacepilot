import { useRef } from 'react';
import type { MouseEvent } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Volume2, 
  VolumeX, 
  ZoomIn, 
  ZoomOut, 
  Layers, 
  Scissors, 
  FastForward, 
  Rewind, 
  ChevronLeft, 
  ChevronRight,
  X
} from 'lucide-react';
import { useTimelineStore } from '../../stores/timelineStore';
import { secondsToSMPTE } from '../../lib/smpte';

export default function TimelineEditor() {
  const { 
    isPlaying, 
    togglePlay, 
    currentTimeSeconds, 
    durationSeconds, 
    seek, 
    tracks,
    zoomLevel,
    setZoomLevel,
    shuttleRate,
    shuttleForward,
    shuttleReverse,
    shuttleStop,
    stepFrames,
    inPoint,
    outPoint,
    setInPoint,
    setOutPoint,
    clearInOutPoints
  } = useTimelineStore();

  const timelineLaneRef = useRef<HTMLDivElement>(null);

  const handleLaneScrub = (e: MouseEvent<HTMLDivElement>) => {
    if (!timelineLaneRef.current) return;
    const rect = timelineLaneRef.current.getBoundingClientRect();
    const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    seek(pos * durationSeconds);
  };

  const getShuttleLabel = () => {
    if (shuttleRate > 0 && shuttleRate !== 1) return `▶▶ ${shuttleRate}.0×`;
    if (shuttleRate < 0) return `◀◀ ${Math.abs(shuttleRate)}.0×`;
    if (isPlaying) return '▶ PLAYING';
    return '❚❚ PAUSED';
  };

  return (
    <div className="bg-[#09090b] border-t border-white/10 flex flex-col h-64 select-none font-mono text-xs shrink-0 z-20">
      {/* Transport Control Header Bar */}
      <div className="h-10 bg-[#111114] border-b border-white/10 px-4 flex items-center justify-between">
        
        {/* Left: Transport Buttons & Frame Stepping */}
        <div className="flex items-center gap-1.5">
          <button 
            onClick={() => seek(0)}
            className="p-1.5 hover:bg-white/10 rounded text-white/60 hover:text-white transition-colors cursor-pointer"
            title="Rewind to start (Home)"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button 
            onClick={shuttleReverse}
            className="p-1.5 hover:bg-white/10 rounded text-white/60 hover:text-white transition-colors cursor-pointer"
            title="Shuttle Reverse (J: -2x / -4x / -8x)"
          >
            <Rewind className="w-3.5 h-3.5" />
          </button>

          <button 
            onClick={() => stepFrames(-1)}
            className="p-1.5 hover:bg-white/10 rounded text-white/60 hover:text-white transition-colors cursor-pointer"
            title="Step 1 Frame Backward (Left Arrow)"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <button 
            onClick={togglePlay}
            className="px-3 py-1 bg-white text-black hover:bg-zinc-200 rounded-md transition-all shadow-[0_0_12px_rgba(255,255,255,0.15)] cursor-pointer flex items-center gap-1 font-bold text-[11px]"
            title="Play / Pause (Space)"
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5 fill-black" /> : <Play className="w-3.5 h-3.5 fill-black ml-0.5" />}
            <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
          </button>

          <button 
            onClick={() => stepFrames(1)}
            className="p-1.5 hover:bg-white/10 rounded text-white/60 hover:text-white transition-colors cursor-pointer"
            title="Step 1 Frame Forward (Right Arrow)"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>

          <button 
            onClick={shuttleForward}
            className="p-1.5 hover:bg-white/10 rounded text-white/60 hover:text-white transition-colors cursor-pointer"
            title="Shuttle Forward (L: 2x / 4x / 8x)"
          >
            <FastForward className="w-3.5 h-3.5" />
          </button>

          <div className="h-4 w-px bg-white/10 mx-1" />

          {/* Shuttle Rate Pill */}
          <div 
            onClick={shuttleStop}
            className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-colors cursor-pointer ${
              shuttleRate !== 0
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                : 'bg-white/5 text-white/50 border-white/10'
            }`}
            title="Click to Stop Shuttle (K)"
          >
            {getShuttleLabel()}
          </div>

          <div className="h-4 w-px bg-white/10 mx-1" />

          {/* In / Out Point Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setInPoint()}
              className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 hover:text-white text-[10px] cursor-pointer"
              title="Set In Point (I)"
            >
              Mark In
            </button>
            <button
              onClick={() => setOutPoint()}
              className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 hover:text-white text-[10px] cursor-pointer"
              title="Set Out Point (O)"
            >
              Mark Out
            </button>
            {(inPoint !== null || outPoint !== null) && (
              <button
                onClick={clearInOutPoints}
                className="p-1 rounded hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] cursor-pointer ml-0.5"
                title="Clear In/Out Points (Alt+X)"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Center: SMPTE Timecode Display */}
        <div className="flex items-center gap-2.5 bg-black/80 px-3 py-1 rounded-md border border-white/10">
          <span className="text-emerald-400 font-bold text-xs">
            {secondsToSMPTE(currentTimeSeconds)}
          </span>
          <span className="text-white/30">/</span>
          <span className="text-white/60 text-xs">
            {secondsToSMPTE(durationSeconds)}
          </span>
        </div>

        {/* Right: Zoom & Razor Tools */}
        <div className="flex items-center gap-2">
          <button 
            className="p-1.5 hover:bg-white/10 rounded text-white/60 hover:text-white transition-colors cursor-pointer"
            title="Razor Tool (Split Clip)"
          >
            <Scissors className="w-3.5 h-3.5" />
          </button>

          <div className="h-4 w-px bg-white/10 mx-1" />

          <button 
            onClick={() => setZoomLevel(zoomLevel - 0.2)}
            className="p-1 hover:bg-white/10 rounded text-white/50 hover:text-white cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-[10px] text-white/50">{zoomLevel.toFixed(1)}x</span>
          <button 
            onClick={() => setZoomLevel(zoomLevel + 0.2)}
            className="p-1 hover:bg-white/10 rounded text-white/50 hover:text-white cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Tracks Workspace Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Track Headers Sidebar */}
        <div className="w-48 bg-[#09090b] border-r border-white/10 flex flex-col divide-y divide-white/5 shrink-0">
          {tracks.map((track) => (
            <div key={track.id} className="h-14 px-3 flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2 truncate">
                <Layers className="w-3.5 h-3.5 text-white/40 shrink-0" />
                <span className="text-white font-medium truncate">{track.name}</span>
              </div>
              <button className="text-white/40 hover:text-white cursor-pointer p-1">
                {track.muted ? <VolumeX className="w-3.5 h-3.5 text-rose-400" /> : <Volume2 className="w-3.5 h-3.5" />}
              </button>
            </div>
          ))}
        </div>

        {/* Timeline Tracks Lanes & Ruler */}
        <div 
          ref={timelineLaneRef}
          onClick={handleLaneScrub}
          className="flex-1 bg-black overflow-x-auto relative flex flex-col divide-y divide-white/5 cursor-pointer"
        >
          {/* Ruler */}
          <div className="h-6 bg-[#111114] border-b border-white/10 flex items-center px-2 text-[9px] text-white/40 select-none">
            {[0, 1, 2, 3, 4].map((s) => (
              <div key={s} className="flex-1 border-l border-white/10 pl-1 font-mono">
                00:0{s}:00
              </div>
            ))}
          </div>

          {/* Track 1: Video Clip */}
          <div className="h-14 p-1.5 relative">
            <div className="h-full w-full bg-emerald-500/15 border border-emerald-500/40 rounded-md px-3 flex items-center justify-between text-[10px] text-emerald-400 font-bold">
              <span>Take 1 · 4.0s (96 frames @ 24fps) · LTX-2.5 48GB</span>
              <span>ProRes 422</span>
            </div>
          </div>

          {/* Track 2: Voice Audio Waveform */}
          <div className="h-14 p-1.5 relative">
            <div className="h-full w-full bg-purple-500/15 border border-purple-500/40 rounded-md px-3 flex items-center justify-between text-[10px] text-purple-400 font-bold">
              <span>Kokoro Voice (af_bella · 24kHz)</span>
              <span>-16.0 LUFS</span>
            </div>
          </div>

          {/* Track 3: BGM Track */}
          <div className="h-14 p-1.5 relative">
            <div className="h-full w-full bg-cyan-500/15 border border-cyan-500/40 rounded-md px-3 flex items-center justify-between text-[10px] text-cyan-400 font-bold">
              <span>Cyberpunk Ambience (Sidechained Ducking)</span>
              <span>Stereo Master</span>
            </div>
          </div>

          {/* In / Out Point Region Overlay */}
          {inPoint !== null && (
            <div 
              className="absolute top-0 bottom-0 bg-emerald-500/10 border-l-2 border-emerald-400 pointer-events-none z-10"
              style={{
                left: `${(inPoint / durationSeconds) * 100}%`,
                width: outPoint !== null ? `${((outPoint - inPoint) / durationSeconds) * 100}%` : '100%',
              }}
            />
          )}
          {outPoint !== null && inPoint === null && (
            <div 
              className="absolute top-0 bottom-0 bg-emerald-500/10 border-r-2 border-emerald-400 pointer-events-none z-10"
              style={{
                left: '0%',
                width: `${(outPoint / durationSeconds) * 100}%`,
              }}
            />
          )}

          {/* Playhead Indicator */}
          <div 
            className="absolute top-0 bottom-0 w-0.5 bg-rose-500 z-30 pointer-events-none transition-all duration-75"
            style={{ left: `${(currentTimeSeconds / durationSeconds) * 100}%` }}
          >
            <div className="w-2.5 h-2.5 bg-rose-500 -translate-x-[4px] rotate-45 shadow-[0_0_8px_rgba(244,63,94,0.6)]" />
          </div>
        </div>
      </div>
    </div>
  );
}
