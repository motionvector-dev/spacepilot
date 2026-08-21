import { useState, useRef, useEffect } from 'react';
import { 
  User, 
  Bot, 
  Cpu, 
  ChevronDown, 
  Send, 
  Sliders
} from 'lucide-react';
import { useStudioStore } from '../../../stores/studioStore';

export const AgentRightPanel = () => {
  const { 
    chatMessages, 
    addChatMessage,
    motionAmount, 
    setMotionAmount,
    guidanceScale, 
    setGuidanceScale,
    panAngle, 
    setPanAngle,
    setZoomRatio,
    prompt,
    setPrompt
  } = useStudioStore();

  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({
    'msg-2': true,
  });
  const [chatInput, setChatInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const toggleReasoning = (id: string) => {
    setExpandedReasoning((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSend = () => {
    const text = chatInput.trim();
    if (!text) return;

    addChatMessage({
      role: 'user',
      text,
    });
    setChatInput('');

    // Generate intelligent contextual response
    setTimeout(() => {
      let replyText = `I've updated the storyboard configuration based on your feedback.`;
      let tags = ['updated', 'cinematic'];
      let reasoning = `> Processed instruction: "${text}"\n> Adjusting motion vectors and camera guidance.\n> Ready for take audition.`;

      if (text.toLowerCase().includes('more rain') || text.toLowerCase().includes('darker')) {
        replyText = `Amplified volumetric rain density and lowered ambient light level. Contrast ratio set to 12:1.`;
        tags = ['heavy rain', 'high contrast', 'noir lighting'];
        setPrompt(`${prompt}, intense heavy rain, high contrast volumetric shadows`);
      } else if (text.toLowerCase().includes('fast') || text.toLowerCase().includes('speed')) {
        replyText = `Accelerated camera tracking speed and increased Motion Amount to 85.`;
        tags = ['fast tracking', 'dynamic motion', 'high shutter'];
        setMotionAmount(85);
      } else if (text.toLowerCase().includes('zoom') || text.toLowerCase().includes('closer')) {
        replyText = `Adjusted camera zoom ratio to 1.8x for a closer framing.`;
        tags = ['close framing', 'macro depth', 'anamorphic'];
        setZoomRatio(1.8);
      }

      addChatMessage({
        role: 'agent',
        text: replyText,
        reasoning,
        tags,
      });
    }, 600);
  };

  return (
    <aside className="fixed right-0 top-0 bottom-0 w-[320px] bg-[#09090b] border-l border-white/10 z-30 flex flex-col pt-[44px] select-none">
      {/* Panel Header */}
      <div className="h-10 px-4 border-b border-white/10 flex items-center justify-between bg-black/40">
        <div className="flex items-center gap-2 font-mono text-xs text-white/90">
          <Bot className="w-4 h-4 text-emerald-400" />
          <span className="font-bold">Director Agent Chat</span>
        </div>
        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
          Online
        </span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
        {chatMessages.map((msg) => (
          <div key={msg.id} className="flex flex-col gap-1.5">
            {/* Sender Label */}
            <div className="flex items-center gap-2">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center border text-[10px] font-bold ${
                msg.role === 'user'
                  ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                  : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
              }`}>
                {msg.role === 'user' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
              </div>
              <span className="text-xs font-semibold text-white/70 font-sans">
                {msg.role === 'user' ? 'You' : 'AI Director'}
              </span>
              <span className="text-[10px] font-mono text-white/30 ml-auto">
                {msg.timestamp}
              </span>
            </div>

            {/* Message Bubble */}
            <div className={`rounded-xl p-3 text-xs leading-relaxed border ${
              msg.role === 'user'
                ? 'bg-white/5 border-white/10 text-white/90 font-sans'
                : 'bg-[#111114] border-white/15 text-white/90 space-y-2 font-sans shadow-lg'
            }`}>
              <p>{msg.text}</p>

              {/* Reasoning Expander Trace */}
              {msg.reasoning && (
                <div className="border border-white/10 rounded-lg overflow-hidden bg-black/60 mt-2">
                  <button 
                    onClick={() => toggleReasoning(msg.id)}
                    className="flex items-center justify-between w-full p-2 text-[11px] text-white/60 hover:text-white transition-colors bg-white/[0.04] cursor-pointer"
                  >
                    <div className="flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-purple-400" />
                      <span className="font-mono font-medium">Model Reasoning</span>
                    </div>
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expandedReasoning[msg.id] ? 'rotate-180' : ''}`} />
                  </button>
                  {expandedReasoning[msg.id] && (
                    <div className="p-2.5 text-[10px] text-white/60 font-mono leading-relaxed border-t border-white/10 whitespace-pre-line bg-black/80">
                      {msg.reasoning}
                    </div>
                  )}
                </div>
              )}

              {/* Prompt Tags Breakdown */}
              {msg.tags && msg.tags.length > 0 && (
                <div className="pt-2 border-t border-white/10 space-y-1.5">
                  <div className="text-[10px] font-mono text-white/40 uppercase tracking-wider">
                    Prompt Structure:
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {msg.tags.map((tag, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          if (!prompt.includes(tag)) {
                            setPrompt(`${prompt}, ${tag}`);
                          }
                        }}
                        className="px-2 py-0.5 rounded bg-white/5 hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/30 text-white/70 hover:text-emerald-400 text-[10px] font-mono transition-all cursor-pointer"
                        title="Click to append keyword to prompt"
                      >
                        +{tag}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Live STG & Motion Parameter Sliders */}
      <div className="p-3.5 border-t border-white/10 bg-[#111114] space-y-3">
        <div className="flex items-center justify-between text-xs font-mono text-white">
          <span className="font-bold flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-emerald-400" />
            Motion Guidance
          </span>
          <span className="text-[10px] text-white/40">Realtime</span>
        </div>

        {/* Motion Amount */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-white/60">Motion Amount</span>
            <span className="text-emerald-400 font-bold">{motionAmount}</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={motionAmount}
            onChange={(e) => setMotionAmount(Number(e.target.value))}
            className="w-full accent-emerald-400 cursor-pointer h-1 bg-white/10 rounded"
          />
        </div>

        {/* Guidance Scale */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-white/60">Guidance Scale (CFG)</span>
            <span className="text-cyan-400 font-bold">{guidanceScale.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="1.0"
            max="20.0"
            step="0.5"
            value={guidanceScale}
            onChange={(e) => setGuidanceScale(Number(e.target.value))}
            className="w-full accent-cyan-400 cursor-pointer h-1 bg-white/10 rounded"
          />
        </div>

        {/* Camera Pan Orbit */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-white/60">Camera Orbit (Pan)</span>
            <span className="text-purple-400 font-bold">{panAngle > 0 ? `+${panAngle}°` : `${panAngle}°`}</span>
          </div>
          <input
            type="range"
            min="-45"
            max="45"
            value={panAngle}
            onChange={(e) => setPanAngle(Number(e.target.value))}
            className="w-full accent-purple-400 cursor-pointer h-1 bg-white/10 rounded"
          />
        </div>
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-white/10 bg-[#09090b]">
        <div className="relative flex items-center bg-[#111114] border border-white/10 rounded-xl focus-within:border-white/20 transition-colors">
          <input 
            type="text" 
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            placeholder="Tell agent to adjust scene..." 
            className="w-full bg-transparent text-xs text-white placeholder:text-white/30 outline-none py-2.5 pl-3 pr-9 font-sans"
          />
          <button 
            onClick={handleSend}
            className="absolute right-1.5 w-7 h-7 flex items-center justify-center rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
            title="Send Message"
          >
            <Send className="w-3.5 h-3.5 text-emerald-400" />
          </button>
        </div>
      </div>
    </aside>
  );
};

export default AgentRightPanel;
