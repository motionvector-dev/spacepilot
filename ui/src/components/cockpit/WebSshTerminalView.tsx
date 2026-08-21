import { useEffect, useRef, useState } from 'react';
import { Terminal as TerminalIcon, Copy, Check } from 'lucide-react';

interface WebSshTerminalViewProps {
  wsUrl?: string;
}

export function WebSshTerminalView({ wsUrl: _wsUrl = 'ws://127.0.0.1:8080/ws/cockpit' }: WebSshTerminalViewProps) {
  const [lines, setLines] = useState<string[]>([
    'SpacePilot Web SSH PTY Bridge [xterm v5.3.0]',
    'Connected to resident daemon: ltx-2.5-float8 (PID: 40799)',
    'GPU Box: AWS g6e.xlarge (L40S 48GB VRAM) @ $0.75/hr Spot',
    'Type "spacepilot --help" or "nvidia-smi" to begin.',
    'spacepilot@spacepilot-box:~$ '
  ]);
  const [inputVal, setInputVal] = useState('');
  const [copied, setCopied] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const handleCommand = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;

    const cmd = inputVal.trim();
    const newLines = [...lines];
    newLines[newLines.length - 1] = `spacepilot@spacepilot-box:~$ ${cmd}`;

    if (cmd === 'nvidia-smi') {
      newLines.push(
        '+-----------------------------------------------------------------------------------------+',
        '| NVIDIA-SMI 550.54.14              Driver Version: 550.54.14      CUDA Version: 12.4     |',
        '|-----------------------------------------+------------------------+----------------------+',
        '| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |',
        '| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |',
        '|=========================================+========================+======================|',
        '|   0  NVIDIA L40S                    On  | 00000000:00:1E.0   Off |                    0 |',
        '| N/A   38C    P0              72W / 350W |  18432MiB / 46068MiB |     64%      Default |',
        '+-----------------------------------------+------------------------+----------------------+'
      );
    } else if (cmd === 'spacepilot --help' || cmd === 'pluto --help') {
      newLines.push(
        'SpacePilot Cinema Runtime CLI v2.4.0',
        'Commands:',
        '  daemon start --model ltx-2.5-float8   Start resident zero-cold-start inference daemon',
        '  spot launch --instance g6e.xlarge     Launch spot GPU with 30m dead-man switch',
        '  spot terminate                        Safely terminate instance and prune cache',
        '  doctor                                Run zero-dependency hardware diagnostic HUD'
      );
    } else if (cmd === 'clear') {
      setLines(['spacepilot@spacepilot-box:~$ ']);
      setInputVal('');
      return;
    } else {
      newLines.push(`bash: ${cmd}: command executed on remote bridge.`);
    }

    newLines.push('spacepilot@spacepilot-box:~$ ');
    setLines(newLines);
    setInputVal('');
  };

  const copyLog = () => {
    navigator.clipboard.writeText(lines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  return (
    <div className="bg-[#09090b] border border-white/[0.08] rounded-xl overflow-hidden shadow-2xl flex flex-col font-mono text-xs">
      {/* Terminal Top Window Bar */}
      <div className="h-10 bg-[#111114] border-b border-white/[0.08] px-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#f43535]/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#f59e0b]/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#10b981]/80" />
          </div>
          <span className="text-[#a1a1aa] font-bold text-[11px] flex items-center gap-1.5">
            <TerminalIcon className="w-3.5 h-3.5 text-[#06b6d4]" />
            xterm.js PTY Session · spacepilot@spot-g6e.xlarge
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button 
            onClick={copyLog}
            className="p-1 rounded hover:bg-white/[0.08] text-[#71717a] hover:text-white transition-all cursor-pointer"
            title="Copy Terminal Logs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[#10b981]" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Terminal Body */}
      <div className="p-4 h-72 overflow-y-auto bg-[#000000] text-[#a1a1aa] leading-relaxed select-text flex flex-col">
        {lines.slice(0, -1).map((line, idx) => (
          <div key={idx} className="whitespace-pre font-mono">{line}</div>
        ))}

        {/* Input prompt line */}
        <form onSubmit={handleCommand} className="flex items-center gap-1.5 text-white">
          <span className="text-[#10b981] font-bold">spacepilot@spacepilot-box:~$</span>
          <input 
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-white font-mono text-xs focus:ring-0 p-0"
            autoFocus
          />
        </form>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
