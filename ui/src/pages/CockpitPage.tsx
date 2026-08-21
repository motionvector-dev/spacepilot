import { useState } from 'react';
import { 
  Terminal, 
  Cpu, 
  HardDrive, 
  Activity, 
  ShieldCheck, 
  Power, 
  RefreshCw, 
  Radio
} from 'lucide-react';
import { useGpuStore } from '../stores/gpuStore';

export default function CockpitPage() {
  const { status: gpu, isLaunching, launchGpu, terminateGpu } = useGpuStore();
  const [command, setCommand] = useState('');
  const [logs, setLogs] = useState<string[]>([
    '[23:25:01] [SYSTEM] SpacePilot WebSocket PTY bridge connected to /dev/pts/2',
    '[23:25:02] [GPU] NVIDIA L40S 48GB detected. Driver 550.54.14 | CUDA 12.4',
    '[23:25:03] [DAEMON] LTX-2.5 quantized float8_e4m3fn resident in VRAM (18.4GB / 48.0GB)',
    '[23:25:04] [AUDIO] Kokoro-82M ONNX model initialized with EBU R128 (-16 LUFS) normalization',
    '[23:25:05] [WATCHDOG] Dead Man Switch active. Idle timeout set to 30m00s.',
    '[23:25:06] [FASTMCP] FastMCP Tool Server registered 6 cinema directives. Listening on :8000/sse'
  ]);

  const handleCommandSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;
    setLogs((prev) => [...prev, `$ ${command}`, `[PTY] Executed: ${command} (exit 0)`]);
    setCommand('');
  };

  return (
    <div className="min-h-screen bg-black text-[#fafafa] flex flex-col font-sans">
      {/* Top Header */}
      <header className="h-14 bg-[#09090b] border-b border-white/[0.08] px-6 flex items-center justify-between z-20">
        <div className="flex items-center gap-4">
          <a href="/" className="flex items-center gap-2 text-sm font-extrabold tracking-tight">
            <span>🛸</span>
            <span>SpacePilot Cockpit</span>
          </a>
          <div className="h-4 w-px bg-white/[0.1]" />
          <div className="flex items-center gap-2 font-mono text-xs text-[#a1a1aa]">
            <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
            <span>Node: spot-g6e.xlarge (L40S 48GB)</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button 
            onClick={launchGpu}
            disabled={isLaunching}
            className="flex items-center gap-1.5 text-xs font-mono bg-[#18181b] hover:bg-[#222226] border border-white/[0.1] px-3 py-1.5 rounded text-[#a1a1aa] hover:text-white transition-all cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLaunching ? 'animate-spin' : ''}`} />
            Reboot Daemon
          </button>
          <button 
            onClick={terminateGpu}
            className="flex items-center gap-1.5 text-xs font-semibold bg-[#f43f5e]/15 border border-[#f43f5e]/40 text-[#f43f5e] hover:bg-[#f43f5e]/25 px-4 py-1.5 rounded transition-all cursor-pointer"
          >
            <Power className="w-3.5 h-3.5" />
            Release Node
          </button>
        </div>
      </header>

      {/* Cockpit Telemetry & Web SSH Grid */}
      <main className="flex-1 p-6 grid grid-cols-12 gap-6 overflow-hidden max-w-7xl mx-auto w-full">
        {/* Telemetry Stat Cards */}
        <div className="col-span-12 grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="bg-[#09090b] border border-white/[0.08] rounded-xl p-4 flex flex-col justify-between">
            <div className="flex justify-between items-center text-[#71717a] font-mono text-xs">
              <span>VRAM Usage</span>
              <Cpu className="w-4 h-4 text-[#10b981]" />
            </div>
            <div className="my-2">
              <div className="text-2xl font-extrabold text-white font-mono">
                {gpu.vramUsedGb} <span className="text-xs text-[#71717a]">/ {gpu.vramTotalGb} GB</span>
              </div>
              <div className="w-full bg-[#18181b] h-1.5 rounded-full mt-2 overflow-hidden">
                <div className="bg-[#10b981] h-full rounded-full" style={{ width: `${(gpu.vramUsedGb / gpu.vramTotalGb) * 100}%` }} />
              </div>
            </div>
            <span className="font-mono text-[10px] text-[#10b981]">0.0s Resident Daemon</span>
          </div>

          <div className="bg-[#09090b] border border-white/[0.08] rounded-xl p-4 flex flex-col justify-between">
            <div className="flex justify-between items-center text-[#71717a] font-mono text-xs">
              <span>GPU Load</span>
              <Activity className="w-4 h-4 text-[#06b6d4]" />
            </div>
            <div className="my-2">
              <div className="text-2xl font-extrabold text-white font-mono">{gpu.gpuUtilization}%</div>
              <div className="w-full bg-[#18181b] h-1.5 rounded-full mt-2 overflow-hidden">
                <div className="bg-[#06b6d4] h-full rounded-full" style={{ width: `${gpu.gpuUtilization}%` }} />
              </div>
            </div>
            <span className="font-mono text-[10px] text-[#a1a1aa]">SM Clock 2520 MHz</span>
          </div>

          <div className="bg-[#09090b] border border-white/[0.08] rounded-xl p-4 flex flex-col justify-between">
            <div className="flex justify-between items-center text-[#71717a] font-mono text-xs">
              <span>Spot Hourly Cost</span>
              <HardDrive className="w-4 h-4 text-[#f59e0b]" />
            </div>
            <div className="my-2">
              <div className="text-2xl font-extrabold text-[#f59e0b] font-mono">${gpu.hourlyCostUsd} <span className="text-xs text-[#71717a]">/ hr</span></div>
              <div className="font-mono text-xs text-[#a1a1aa] mt-1">AWS Spot Arbitrage</div>
            </div>
            <span className="font-mono text-[10px] text-[#10b981]">Saved 78% vs On-Demand</span>
          </div>

          <div className="bg-[#09090b] border border-white/[0.08] rounded-xl p-4 flex flex-col justify-between">
            <div className="flex justify-between items-center text-[#71717a] font-mono text-xs">
              <span>Dead Man Switch</span>
              <ShieldCheck className="w-4 h-4 text-[#a855f7]" />
            </div>
            <div className="my-2">
              <div className="text-2xl font-extrabold text-white font-mono">23m 40s</div>
              <div className="font-mono text-xs text-[#a1a1aa] mt-1">Idle Auto-Termination</div>
            </div>
            <span className="font-mono text-[10px] text-[#10b981]">Watchdog Active</span>
          </div>
        </div>

        {/* Web SSH Terminal (xterm.js style) */}
        <div className="col-span-12 bg-[#09090b] border border-white/[0.12] rounded-xl flex flex-col overflow-hidden shadow-2xl h-[480px]">
          <div className="h-10 bg-[#111114] border-b border-white/[0.08] px-4 flex items-center justify-between font-mono text-xs text-[#71717a]">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-white/[0.15]" />
                <div className="w-2.5 h-2.5 rounded-full bg-white/[0.15]" />
                <div className="w-2.5 h-2.5 rounded-full bg-white/[0.15]" />
              </div>
              <span className="ml-2 font-bold text-white flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-[#38bdf8]" />
                cockpit-pty-session · /dev/pts/2
              </span>
            </div>
            <div className="flex items-center gap-2 text-[10px] text-[#10b981]">
              <Radio className="w-3 h-3 text-[#10b981]" />
              WEBSOCKET CONNECTED
            </div>
          </div>

          <div className="flex-1 bg-black p-4 font-mono text-xs leading-relaxed overflow-y-auto text-[#38bdf8] flex flex-col justify-between">
            <div className="flex flex-col gap-1">
              {logs.map((log, index) => (
                <div key={index} className="whitespace-pre-wrap">
                  {log}
                </div>
              ))}
            </div>

            <form onSubmit={handleCommandSubmit} className="flex items-center gap-2 mt-4 pt-2 border-t border-white/[0.06]">
              <span className="text-[#10b981] font-bold">spacepilot@spot-g6e:~$</span>
              <input 
                type="text"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="Type command (e.g. nvidia-smi, ps aux, cat /tmp/daemon.log)..."
                className="flex-1 bg-transparent border-none outline-none text-white font-mono text-xs"
              />
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
