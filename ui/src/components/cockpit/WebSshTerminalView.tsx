import { useEffect, useRef, useState } from 'react';
import { 
  Terminal as TerminalIcon, 
  Copy, 
  Check, 
  Wifi, 
  WifiOff, 
  Maximize2, 
  Minimize2, 
  Trash2, 
  ZoomIn, 
  ZoomOut, 
  Pause, 
  Play, 
  RotateCw, 
  Radio,
  FileText
} from 'lucide-react';
import { useInspectAction, fetchToken } from '../../hooks/useGpuStatus';

interface WebSshTerminalViewProps {
  wsUrl?: string;
  streamUrl?: string;
}

export function WebSshTerminalView({ 
  wsUrl = 'ws://127.0.0.1:8088/api/gpu/inspect/shell',
  streamUrl = '/api/gpu/logs/stream'
}: WebSshTerminalViewProps) {
  const [activeTab, setActiveTab] = useState<'stream' | 'shell'>('stream');
  const [lines, setLines] = useState<string[]>([
    '[Cockpit] Initializing live telemetry and log stream...',
    '[Cockpit] Connected to remote spot worker (/scratch/worker/worker.log)',
  ]);
  const [inputVal, setInputVal] = useState('');
  const [copied, setCopied] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fontSize, setFontSize] = useState<number>(11); // 10, 11, 12, 13, 14, 16

  const wsRef = useRef<WebSocket | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inspectActionMutation = useInspectAction();

  // 1. SSE Remote Worker Log Stream
  useEffect(() => {
    if (activeTab !== 'stream') {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    try {
      const es = new EventSource(streamUrl);
      eventSourceRef.current = es;

      es.onopen = () => {
        setIsConnected(true);
      };

      es.onmessage = (e) => {
        if (isPaused) return;
        try {
          const data = JSON.parse(e.data);
          setLines(prev => [...prev.slice(-400), data.line || e.data]);
        } catch {
          setLines(prev => [...prev.slice(-400), e.data]);
        }
      };

      es.onerror = () => {
        setIsConnected(false);
      };
    } catch {
      setIsConnected(false);
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [activeTab, streamUrl, isPaused]);

  // 2. Interactive WebSocket PTY Shell
  useEffect(() => {
    if (activeTab !== 'shell') {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    let cancelled = false;

    (async () => {
      const token = await fetchToken();
      if (cancelled) return;

      // No explicit ack for the auth frame — the first frame the backend
      // sends back (real PTY output, or its own {"type":"error",...}) is
      // the only proof it got past auth and didn't just 1008-close us.
      let connected = false;

      try {
        const targetUrl = wsUrl.startsWith('ws')
          ? wsUrl
          : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${wsUrl}`;

        const ws = new WebSocket(targetUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          // gpu.py's inspect_shell_ws requires this as the first message,
          // within 3s, or it closes with code 1008.
          ws.send(JSON.stringify({ type: 'auth', token }));
        };

        ws.onmessage = (event) => {
          if (isPaused) return;
          const text = typeof event.data === 'string' ? event.data : '';
          if (!text) return;

          let errorMessage: string | null = null;
          try {
            const parsed = JSON.parse(text);
            if (parsed && parsed.type === 'error') errorMessage = parsed.message || 'Remote error';
          } catch {
            // not JSON: raw PTY bytes
          }

          if (errorMessage) {
            setLines(prev => [...prev.slice(-400), `[ERROR] ${errorMessage}`]);
            return;
          }

          if (!connected) {
            connected = true;
            setIsConnected(true);
            setLines(prev => [...prev.slice(-400), '[CONNECTED] Remote PTY bridge established. Type commands below.']);
          }

          const splitLines = text.split('\n');
          setLines(prev => [...prev.slice(-400), ...splitLines]);
        };

        ws.onerror = () => {
          setIsConnected(false);
          setLines(prev => [...prev, '[ERROR] WebSocket connection error. Backend PTY unreachable.']);
        };

        ws.onclose = (event) => {
          setIsConnected(false);
          setLines(prev => [
            ...prev,
            event.code === 1008
              ? '[ERROR] Authentication rejected by backend PTY bridge.'
              : '[DISCONNECTED] PTY bridge closed.',
          ]);
        };
      } catch {
        setIsConnected(false);
      }
    })();

    return () => {
      cancelled = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [activeTab, wsUrl, isPaused]);

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
        `ubuntu@gpu-box:~$ ${cmd}`,
        `[OFFLINE/READ-ONLY] Executed in local sandbox: "${cmd}"`
      ]);
    }

    setInputVal('');
  };

  const copyLog = () => {
    navigator.clipboard.writeText(lines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const clearBuffer = () => {
    setLines([]);
  };

  const togglePause = () => {
    setIsPaused(!isPaused);
  };

  const increaseFontSize = () => {
    setFontSize(prev => Math.min(16, prev + 1));
  };

  const decreaseFontSize = () => {
    setFontSize(prev => Math.max(10, prev - 1));
  };

  const handleServiceAction = async (action: 'restart_worker' | 'clear_tmp') => {
    setLines(prev => [...prev, `[Cockpit] Executing service action: ${action}...`]);
    try {
      await inspectActionMutation.mutateAsync(action);
      setLines(prev => [...prev, `[Cockpit] Service action ${action} completed successfully.`]);
    } catch (err: any) {
      setLines(prev => [...prev, `[Cockpit] Error executing ${action}: ${err.message}`]);
    }
  };

  useEffect(() => {
    if (isPaused) return;
    // Scroll the log's own box, not the document. scrollIntoView walks up every
    // scrollable ancestor including <html>, so each appended line dragged the
    // whole page down to whatever sits below the terminal — the disk gauge —
    // no matter where the reader had scrolled to.
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines, isPaused]);

  const containerClasses = isFullscreen
    ? 'fixed inset-0 z-50 bg-[#000000] p-6 flex flex-col'
    : 'bg-[#09090b] border border-white/10 rounded-2xl overflow-hidden shadow-2xl flex flex-col';

  return (
    <div className={containerClasses}>
      {/* Terminal Top Window Bar */}
      <div className="h-11 bg-[#111114] border-b border-white/10 px-4 flex items-center justify-between gap-2 flex-wrap">
        {/* Left: Window Dots & Mode Tabs */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#f43535]/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#f59e0b]/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#10b981]/80" />
          </div>

          <div className="flex items-center bg-[#18181b] border border-white/10 rounded-lg p-0.5 ml-2">
            <button
              onClick={() => setActiveTab('stream')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'stream'
                  ? 'bg-white/10 text-[#fafafa] shadow-sm'
                  : 'text-[#71717a] hover:text-[#a1a1aa]'
              }`}
            >
              <Radio className="w-3 h-3 text-[#10b981]" />
              <span>Worker Log Stream</span>
            </button>

            <button
              onClick={() => setActiveTab('shell')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === 'shell'
                  ? 'bg-white/10 text-[#fafafa] shadow-sm'
                  : 'text-[#71717a] hover:text-[#a1a1aa]'
              }`}
            >
              <TerminalIcon className="w-3 h-3 text-[#06b6d4]" />
              <span>Web SSH Shell</span>
            </button>
          </div>
        </div>

        {/* Right Controls: Font Scaling, Pause, Clear, Copy, Fullscreen, Service Actions */}
        <div className="flex items-center gap-2">
          {/* Status Indicator */}
          <span className="flex items-center gap-1 text-[10.5px] font-mono text-[#71717a] mr-1 hidden sm:flex">
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

          {/* Quick Service Actions */}
          <div className="hidden md:flex items-center gap-1 border-r border-white/10 pr-2 mr-1">
            <button
              onClick={() => handleServiceAction('restart_worker')}
              disabled={inspectActionMutation.isPending}
              className="text-[10.5px] font-mono font-semibold px-2 py-0.5 rounded bg-white/5 text-[#a1a1aa] hover:text-[#fafafa] hover:bg-white/10 transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50"
              title="Restart resident LTX worker systemd service"
            >
              <RotateCw className="w-3 h-3 text-[#3b82f6]" />
              <span>Restart Worker</span>
            </button>
            <button
              onClick={() => handleServiceAction('clear_tmp')}
              disabled={inspectActionMutation.isPending}
              className="text-[10.5px] font-mono font-semibold px-2 py-0.5 rounded bg-white/5 text-[#f43535]/80 hover:text-[#f43535] hover:bg-[#f43535]/10 transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50"
              title="Purge /scratch/tmp temporary files"
            >
              <Trash2 className="w-3 h-3 text-[#f43535]" />
              <span>Purge Tmp</span>
            </button>
          </div>

          {/* Font-Size Scaling */}
          <div className="flex items-center bg-[#18181b] border border-white/10 rounded-md p-0.5">
            <button
              onClick={decreaseFontSize}
              className="p-1 rounded text-[#71717a] hover:text-[#fafafa] transition-colors cursor-pointer"
              title="Decrease Font Size"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[10px] font-mono px-1.5 text-[#a1a1aa] font-bold select-none">
              {fontSize}px
            </span>
            <button
              onClick={increaseFontSize}
              className="p-1 rounded text-[#71717a] hover:text-[#fafafa] transition-colors cursor-pointer"
              title="Increase Font Size"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Pause Stream Button */}
          <button
            onClick={togglePause}
            className={`p-1.5 rounded border transition-all cursor-pointer ${
              isPaused 
                ? 'bg-[#f59e0b]/20 text-[#f59e0b] border-[#f59e0b]/40' 
                : 'border-white/10 text-[#71717a] hover:text-white hover:bg-white/10'
            }`}
            title={isPaused ? 'Resume Stream' : 'Pause Stream'}
          >
            {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
          </button>

          {/* Clear Buffer Button */}
          <button
            onClick={clearBuffer}
            className="p-1.5 rounded border border-white/10 text-[#71717a] hover:text-white hover:bg-white/10 transition-all cursor-pointer"
            title="Clear Terminal Buffer"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>

          {/* Copy Buffer Button */}
          <button 
            onClick={copyLog}
            className="p-1.5 rounded border border-white/10 text-[#71717a] hover:text-white hover:bg-white/10 transition-all cursor-pointer"
            title="Copy Terminal Logs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[#10b981]" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          {/* Fullscreen Toggle */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 rounded border border-white/10 text-[#71717a] hover:text-white hover:bg-white/10 transition-all cursor-pointer"
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Terminal'}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5 text-[#3b82f6]" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Terminal Body */}
      <div 
        style={{ fontSize: `${fontSize}px` }}
        ref={logRef}
        className={`p-4 overflow-y-auto bg-[#000000] text-[#a1a1aa] leading-relaxed select-text flex flex-col font-mono ${
          isFullscreen ? 'flex-1 h-full' : 'h-80'
        }`}
      >
        {lines.length === 0 ? (
          <div className="text-[#52525b] italic py-8 text-center flex items-center justify-center gap-2">
            <FileText className="w-4 h-4 text-[#52525b]" />
            <span>Terminal buffer cleared. Waiting for remote events...</span>
          </div>
        ) : (
          lines.map((line, idx) => (
            <div 
              key={idx} 
              className={`whitespace-pre-wrap ${
                line.includes('[ERROR]') || line.includes('error') ? 'text-[#f43535]' :
                line.includes('[CONNECTED]') || line.includes('success') ? 'text-[#10b981]' :
                line.includes('[Cockpit]') ? 'text-[#06b6d4]' :
                line.includes('warning') ? 'text-[#f59e0b]' :
                'text-[#a1a1aa]'
              }`}
            >
              {line}
            </div>
          ))
        )}

        {/* Input prompt line (shown in interactive shell mode) */}
        {activeTab === 'shell' && (
          <form onSubmit={handleCommand} className="flex items-center gap-1.5 text-white mt-2">
            <span className="text-[#10b981] font-bold select-none">ubuntu@gpu-box:~$</span>
            <input 
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Enter shell command (e.g. nvidia-smi, df -h, tail -f /scratch/worker/worker.log)"
              className="flex-1 bg-transparent border-none outline-none text-white font-mono focus:ring-0 p-0"
              autoFocus
            />
          </form>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

