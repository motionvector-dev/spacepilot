import { useEffect, useRef, useState } from 'react';
import { Terminal as TerminalIcon, Copy, Check, Wifi, WifiOff } from 'lucide-react';

interface WebSshTerminalViewProps {
  wsUrl?: string;
}

export function WebSshTerminalView({ wsUrl = 'ws://127.0.0.1:8088/api/gpu/inspect/shell' }: WebSshTerminalViewProps) {
  const [lines, setLines] = useState<string[]>([
    'Connecting to resident PTY bridge...',
  ]);
  const [inputVal, setInputVal] = useState('');
  const [copied, setCopied] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let ws: WebSocket;
    try {
      const targetUrl = wsUrl.startsWith('ws') 
        ? wsUrl 
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${wsUrl}`;

      ws = new WebSocket(targetUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setLines(prev => [...prev, '[CONNECTED] Remote PTY bridge established.']);
      };

      ws.onmessage = (event) => {
        const text = typeof event.data === 'string' ? event.data : '';
        if (text) {
          const splitLines = text.split('\n');
          setLines(prev => [...prev, ...splitLines]);
        }
      };

      ws.onerror = () => {
        setIsConnected(false);
        setLines(prev => [...prev, '[ERROR] WebSocket connection error. Backend PTY unreachable.']);
      };

      ws.onclose = () => {
        setIsConnected(false);
        setLines(prev => [...prev, '[DISCONNECTED] PTY bridge closed.']);
      };
    } catch {
      setIsConnected(false);
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [wsUrl]);

  const handleCommand = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;

    const cmd = inputVal;
    if (cmd === 'clear') {
      setLines([]);
      setInputVal('');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(cmd + '\n');
    } else {
      setLines(prev => [
        ...prev, 
        `spacepilot@box:~$ ${cmd}`,
        `[OFFLINE] Cannot execute "${cmd}" — WebSocket not connected.`
      ]);
    }

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
            xterm PTY Bridge · {isConnected ? 'ws://localhost:8088' : 'offline'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-[10px] text-[#71717a]">
            {isConnected ? (
              <span className="flex items-center gap-1 text-[#10b981]">
                <Wifi className="w-3 h-3" /> Live
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[#f59e0b]">
                <WifiOff className="w-3 h-3" /> Standby
              </span>
            )}
          </span>
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
      <div className="p-4 h-72 overflow-y-auto bg-[#000000] text-[#a1a1aa] leading-relaxed select-text flex flex-col font-mono text-[11px]">
        {lines.map((line, idx) => (
          <div key={idx} className="whitespace-pre-wrap">{line}</div>
        ))}

        {/* Input prompt line */}
        <form onSubmit={handleCommand} className="flex items-center gap-1.5 text-white mt-1">
          <span className="text-[#10b981] font-bold">spacepilot@box:~$</span>
          <input 
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-white font-mono text-[11px] focus:ring-0 p-0"
            autoFocus
          />
        </form>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
