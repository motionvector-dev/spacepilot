import { useEngines } from '../../hooks/useCompute';
import { 
  Shuffle, 
  Lock, 
  Unlock, 
  Sliders, 
  Compass, 
  ChevronUp, 
  ChevronDown, 
  ChevronLeft, 
  ChevronRight
} from 'lucide-react';

interface ModelEngineStepProps {
  selectedEngine: string;
  setSelectedEngine: (id: string) => void;
  computeTarget: 'auto' | 'local' | 'spot';
  setComputeTarget: (target: 'auto' | 'local' | 'spot') => void;
  engineQuality: 'pro' | 'draft';
  setEngineQuality: (q: 'pro' | 'draft') => void;
  aspect: string;
  setAspect: (a: string) => void;
  duration: number;
  setDuration: (d: number) => void;
  fps: number;
  setFps: (fps: number) => void;
  stg: number;
  setStg: (stg: number) => void;
  seed: number;
  setSeed: (s: number) => void;
  isSeedLocked: boolean;
  setIsSeedLocked: (locked: boolean) => void;
  cameraPan: 'static' | 'left' | 'right';
  setCameraPan: (pan: 'static' | 'left' | 'right') => void;
  cameraTilt: 'static' | 'up' | 'down';
  setCameraTilt: (tilt: 'static' | 'up' | 'down') => void;
  cameraZoom: 'static' | 'in' | 'out';
  setCameraZoom: (zoom: 'static' | 'in' | 'out') => void;
  cameraRoll: 'none' | 'left' | 'orbit';
  setCameraRoll: (roll: 'none' | 'left' | 'orbit') => void;
  cameraIntensity: number;
  setCameraIntensity: (i: number) => void;
}

export function ModelEngineStep({
  selectedEngine,
  setSelectedEngine,
  computeTarget,
  setComputeTarget,
  engineQuality,
  setEngineQuality,
  aspect,
  setAspect,
  duration,
  setDuration,
  fps,
  setFps,
  stg,
  setStg,
  seed,
  setSeed,
  isSeedLocked,
  setIsSeedLocked,
  cameraPan,
  setCameraPan,
  cameraTilt,
  setCameraTilt,
  cameraZoom,
  setCameraZoom,
  cameraRoll,
  setCameraRoll,
  cameraIntensity,
  setCameraIntensity,
}: ModelEngineStepProps) {
  const { data: enginesData } = useEngines();

  const fallbackEngines = [
    { id: 'ltx-2.5', name: 'LTX-2.5 Video Generation', vram: '10GB', time: '~18s', color: 'purple' },
    { id: 'wan-14b', name: 'Wan2.1 14B High-Fidelity', vram: '18GB', time: '~45s', color: 'emerald' },
    { id: 'wan-1.3b', name: 'Wan2.1 1.3B Real-Time', vram: '8GB', time: '~12s', color: 'cyan' },
    { id: 'hunyuan', name: 'HunyuanVideo DiT', vram: '16GB', time: '~35s', color: 'amber' },
  ];

  const engines = enginesData && enginesData.length > 0 
    ? enginesData.map((e, idx) => ({
        id: e.id,
        name: e.name,
        vram: `${e.vram_requirement_gb}GB`,
        time: `~${e.cold_start_seconds}s`,
        color: ['purple', 'emerald', 'cyan', 'amber'][idx % 4],
      }))
    : fallbackEngines;

  const colorMap: Record<string, string> = {
    emerald: 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]',
    cyan: 'bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.6)]',
    amber: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]',
    purple: 'bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]',
  };

  // Calculate total frames
  const totalFrames = Math.floor((duration * fps - 1) / 8) * 8 + 1;

  // Gimbal dot offset
  let gimbalX = 0;
  let gimbalY = 0;
  if (cameraPan === 'left') gimbalX = -12;
  if (cameraPan === 'right') gimbalX = 12;
  if (cameraTilt === 'up') gimbalY = -12;
  if (cameraTilt === 'down') gimbalY = 12;

  // Camera preview descriptor
  const cameraMotions: string[] = [];
  if (cameraPan !== 'static') cameraMotions.push(`Pan ${cameraPan.toUpperCase()}`);
  if (cameraTilt !== 'static') cameraMotions.push(`Tilt ${cameraTilt.toUpperCase()}`);
  if (cameraZoom !== 'static') cameraMotions.push(`Zoom ${cameraZoom.toUpperCase()}`);
  if (cameraRoll !== 'none') cameraMotions.push(cameraRoll === 'orbit' ? 'Orbit 360°' : `Roll ${cameraRoll.toUpperCase()}`);

  const cameraDescriptor = cameraMotions.length > 0
    ? `${cameraMotions.join(' + ')} · Intensity ${cameraIntensity}/5`
    : 'Static 3D Camera · 0.0 rad';

  const handleRandomizeSeed = () => {
    const randomSeed = Math.floor(Math.random() * 900000) + 100000;
    setSeed(randomSeed);
  };

  return (
    <div className="flex flex-col gap-5 p-5 bg-[#09090b] border border-white/[0.08] rounded-xl shadow-sm">
      <div className="flex justify-between items-center border-b border-white/[0.06] pb-3">
        <div className="flex items-center gap-2">
          <Sliders className="w-4 h-4 text-white/60" />
          <h2 className="text-[13px] font-semibold text-white/70 uppercase tracking-wider">Engine &amp; Controls</h2>
        </div>
        <span className="text-[11px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
          Resident DiT
        </span>
      </div>

      {/* 1. Model Engine Selector */}
      <div className="flex flex-col gap-2">
        <label className="text-[11px] font-bold text-white/50 uppercase tracking-wider">
          Inference Engine
        </label>
        <div className="grid grid-cols-1 gap-2">
          {engines.map(eng => {
            const isSelected = selectedEngine === eng.id;
            return (
              <button
                key={eng.id}
                onClick={() => setSelectedEngine(eng.id)}
                className={`flex flex-col gap-1.5 p-3 rounded-lg border text-left transition-all cursor-pointer ${
                  isSelected 
                    ? 'bg-[#18181b] border-white/25 shadow-sm' 
                    : 'bg-black border-white/[0.08] hover:bg-[#111114] hover:border-white/[0.14]'
                }`}
              >
                <div className="flex justify-between items-center w-full">
                  <span className="font-semibold text-xs text-white">{eng.name}</span>
                  {isSelected && (
                    <div className={`w-2 h-2 rounded-full ${colorMap[eng.color] || colorMap.purple}`} />
                  )}
                </div>
                <div className="flex gap-2 text-[10.5px] font-mono text-white/45">
                  <span>VRAM: {eng.vram}</span>
                  <span>·</span>
                  <span>Cold: {eng.time}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Compute Target & Quality */}
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-bold text-white/50 uppercase tracking-wider">
            Compute Target
          </label>
          <select
            value={computeTarget}
            onChange={(e) => setComputeTarget(e.target.value as 'auto' | 'local' | 'spot')}
            className="w-full bg-black border border-white/[0.14] rounded-lg px-2.5 py-2 text-xs text-white focus:outline-none focus:border-white/30 cursor-pointer"
          >
            <option value="auto">⚡ Auto (Local-First)</option>
            <option value="local">💻 Local GPU ($0.00)</option>
            <option value="spot">☁️ SkyPilot Spot (~$0.04)</option>
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-bold text-white/50 uppercase tracking-wider">
            Engine Quality
          </label>
          <select
            value={engineQuality}
            onChange={(e) => setEngineQuality(e.target.value as 'pro' | 'draft')}
            className="w-full bg-black border border-white/[0.14] rounded-lg px-2.5 py-2 text-xs text-white focus:outline-none focus:border-white/30 cursor-pointer"
          >
            <option value="pro">🎬 Pro Cinema (30s · ~$0.04)</option>
            <option value="draft">⚡ Draft Mode (15s · ~$0.01)</option>
          </select>
        </div>
      </div>

      {/* 3. Aspect Ratio Selector */}
      <div className="flex flex-col gap-1.5">
        <label className="text-[11px] font-bold text-white/50 uppercase tracking-wider">
          Aspect Ratio
        </label>
        <div className="grid grid-cols-4 gap-1.5 bg-black p-1 rounded-lg border border-white/[0.08]">
          {[
            { id: '16:9', label: '16:9' },
            { id: '9:16', label: '9:16' },
            { id: '1:1', label: '1:1' },
            { id: '2.35:1', label: '2.35:1' }
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setAspect(item.id)}
              className={`py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                aspect === item.id
                  ? 'bg-[#18181b] text-white border border-white/[0.14] shadow-sm'
                  : 'text-white/40 hover:text-white/80'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* 4. Duration Slider & Quick Presets */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center text-xs">
          <label className="font-bold text-white/50 uppercase tracking-wider text-[11px]">
            Duration &amp; Length
          </label>
          <span className="font-mono text-cyan-400 font-semibold">{duration.toFixed(1)}s</span>
        </div>
        
        <input 
          type="range"
          min={2.0}
          max={10.0}
          step={0.5}
          value={duration}
          onChange={(e) => setDuration(parseFloat(e.target.value))}
          className="w-full h-1.5 bg-[#18181b] rounded-lg appearance-none cursor-pointer accent-white"
        />

        <div className="flex items-center gap-1.5 justify-between">
          {[2.0, 4.0, 6.0, 8.0, 10.0].map((sec) => (
            <button
              key={sec}
              onClick={() => setDuration(sec)}
              className={`px-2 py-0.5 rounded text-[10.5px] font-mono transition-colors cursor-pointer ${
                duration === sec
                  ? 'bg-white text-black font-bold'
                  : 'bg-black text-white/40 hover:text-white border border-white/[0.08]'
              }`}
            >
              {sec.toFixed(1)}s
            </button>
          ))}
        </div>
      </div>

      {/* 5. FPS Toggle & Frames Readout */}
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between items-center text-xs">
          <label className="font-bold text-white/50 uppercase tracking-wider text-[11px]">
            Framerate (FPS)
          </label>
          <span className="font-mono text-white/40 text-[11px]">
            {duration.toFixed(1)}s = {totalFrames} frames
          </span>
        </div>

        <div className="grid grid-cols-3 gap-1.5 bg-black p-1 rounded-lg border border-white/[0.08]">
          {[24, 30, 60].map((rate) => (
            <button
              key={rate}
              onClick={() => setFps(rate)}
              className={`py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer font-mono ${
                fps === rate
                  ? 'bg-[#18181b] text-white border border-white/[0.14] shadow-sm'
                  : 'text-white/40 hover:text-white/80'
              }`}
            >
              {rate} fps {rate === 24 ? '🎬' : rate === 60 ? '⚡' : ''}
            </button>
          ))}
        </div>
      </div>

      {/* 6. Motion Guidance (STG) / Motion Intensity Slider */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center text-xs">
          <label className="font-bold text-white/50 uppercase tracking-wider text-[11px]">
            Motion Guidance (STG)
          </label>
          <span className="font-mono text-white/90 font-semibold">{stg.toFixed(1)}</span>
        </div>
        <input 
          type="range"
          min={0.0}
          max={2.0}
          step={0.1}
          value={stg}
          onChange={(e) => setStg(parseFloat(e.target.value))}
          className="w-full h-1.5 bg-[#18181b] rounded-lg appearance-none cursor-pointer accent-white"
        />
        <div className="flex justify-between text-[10px] font-mono text-white/30">
          <span>0.0 (Subtle)</span>
          <span>1.0 (Balanced)</span>
          <span>2.0 (Dynamic)</span>
        </div>
      </div>

      {/* 7. Seed Lock & Randomize */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center text-xs">
          <label className="font-bold text-white/50 uppercase tracking-wider text-[11px]">
            Generation Seed
          </label>
          <span className="font-mono text-[11px] text-white/50">
            {isSeedLocked ? 'Locked' : 'Dynamic Auto'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <input 
              type="number"
              value={seed}
              onChange={(e) => setSeed(parseInt(e.target.value, 10) || 0)}
              disabled={!isSeedLocked}
              className="w-full bg-black border border-white/[0.14] rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-white/30 disabled:opacity-50 disabled:bg-[#111114]"
              placeholder="Seed number..."
            />
          </div>

          <button
            type="button"
            onClick={() => setIsSeedLocked(!isSeedLocked)}
            className={`p-2 rounded-lg border text-xs transition-all cursor-pointer ${
              isSeedLocked 
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' 
                : 'bg-[#18181b] border-white/[0.12] text-white/70 hover:text-white'
            }`}
            title={isSeedLocked ? 'Unlock dynamic random seed' : 'Lock current seed'}
          >
            {isSeedLocked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
          </button>

          <button
            type="button"
            onClick={handleRandomizeSeed}
            className="p-2 rounded-lg bg-[#18181b] hover:bg-[#222226] border border-white/[0.12] text-white/80 hover:text-white transition-all cursor-pointer"
            title="Randomize seed (dice)"
          >
            <Shuffle className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 8. 3D Camera Compass Widget */}
      <div className="flex flex-col gap-3 border-t border-white/[0.06] pt-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-1.5">
            <Compass className="w-4 h-4 text-cyan-400" />
            <span className="text-[11px] font-bold text-white/60 uppercase tracking-wider">
              3D Camera Compass
            </span>
          </div>
          <span className="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-1.5 py-0.2 rounded border border-cyan-500/20">
            {cameraPan !== 'static' || cameraTilt !== 'static' ? 'Vector Active' : 'Static'}
          </span>
        </div>

        {/* Compass Direction Grid with Center Gimbal */}
        <div className="flex items-center justify-center p-3 bg-black/60 border border-white/[0.08] rounded-xl">
          <div className="grid grid-cols-3 grid-rows-3 gap-1 w-32 h-32">
            {/* Row 1 */}
            <div />
            <button
              type="button"
              onClick={() => setCameraTilt(cameraTilt === 'up' ? 'static' : 'up')}
              className={`flex items-center justify-center rounded-lg border transition-all cursor-pointer ${
                cameraTilt === 'up'
                  ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.4)]'
                  : 'bg-[#18181b] border-white/[0.08] text-white/60 hover:text-white hover:bg-[#222226]'
              }`}
              title="Tilt Up"
            >
              <ChevronUp className="w-4 h-4" />
            </button>
            <div />

            {/* Row 2 */}
            <button
              type="button"
              onClick={() => setCameraPan(cameraPan === 'left' ? 'static' : 'left')}
              className={`flex items-center justify-center rounded-lg border transition-all cursor-pointer ${
                cameraPan === 'left'
                  ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.4)]'
                  : 'bg-[#18181b] border-white/[0.08] text-white/60 hover:text-white hover:bg-[#222226]'
              }`}
              title="Pan Left"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            {/* Gimbal Center Display */}
            <div className="relative flex items-center justify-center rounded-full bg-[#111114] border border-white/[0.14] overflow-hidden">
              <div 
                className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)] transition-transform duration-200"
                style={{ transform: `translate(${gimbalX}px, ${gimbalY}px)` }}
              />
            </div>

            <button
              type="button"
              onClick={() => setCameraPan(cameraPan === 'right' ? 'static' : 'right')}
              className={`flex items-center justify-center rounded-lg border transition-all cursor-pointer ${
                cameraPan === 'right'
                  ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.4)]'
                  : 'bg-[#18181b] border-white/[0.08] text-white/60 hover:text-white hover:bg-[#222226]'
              }`}
              title="Pan Right"
            >
              <ChevronRight className="w-4 h-4" />
            </button>

            {/* Row 3 */}
            <div />
            <button
              type="button"
              onClick={() => setCameraTilt(cameraTilt === 'down' ? 'static' : 'down')}
              className={`flex items-center justify-center rounded-lg border transition-all cursor-pointer ${
                cameraTilt === 'down'
                  ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.4)]'
                  : 'bg-[#18181b] border-white/[0.08] text-white/60 hover:text-white hover:bg-[#222226]'
              }`}
              title="Tilt Down"
            >
              <ChevronDown className="w-4 h-4" />
            </button>
            <div />
          </div>
        </div>

        {/* Dolly Zoom & Roll/Orbit Controls */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-bold text-white/40 uppercase">Dolly Zoom</span>
            <div className="flex bg-black p-0.5 rounded-md border border-white/[0.08]">
              {(['in', 'static', 'out'] as const).map((z) => (
                <button
                  key={z}
                  type="button"
                  onClick={() => setCameraZoom(z)}
                  className={`flex-1 py-1 text-[10.5px] font-semibold rounded capitalize transition-colors cursor-pointer ${
                    cameraZoom === z
                      ? 'bg-[#18181b] text-white border border-white/[0.12]'
                      : 'text-white/40 hover:text-white'
                  }`}
                >
                  {z === 'static' ? 'Off' : z}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-bold text-white/40 uppercase">Roll / Orbit</span>
            <div className="flex bg-black p-0.5 rounded-md border border-white/[0.08]">
              {(['none', 'left', 'orbit'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setCameraRoll(r)}
                  className={`flex-1 py-1 text-[10.5px] font-semibold rounded capitalize transition-colors cursor-pointer ${
                    cameraRoll === r
                      ? 'bg-[#18181b] text-white border border-white/[0.12]'
                      : 'text-white/40 hover:text-white'
                  }`}
                >
                  {r === 'none' ? 'Off' : r === 'orbit' ? 'Orbit' : 'Roll'}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Camera Intensity Slider */}
        <div className="flex flex-col gap-1.5 mt-1">
          <div className="flex justify-between items-center text-[10px] font-mono text-white/40 uppercase">
            <span>Vector Intensity</span>
            <span className="text-white/80 font-bold">{cameraIntensity}/5</span>
          </div>
          <input 
            type="range"
            min={1}
            max={5}
            step={1}
            value={cameraIntensity}
            onChange={(e) => setCameraIntensity(parseInt(e.target.value, 10))}
            className="w-full h-1 bg-[#18181b] rounded-lg appearance-none cursor-pointer accent-cyan-400"
          />
        </div>

        {/* Descriptor Preview */}
        <div className="text-center font-mono text-[11px] text-cyan-400 bg-cyan-500/5 border border-cyan-500/15 py-1.5 px-2 rounded-lg">
          {cameraDescriptor}
        </div>
      </div>
    </div>
  );
}
