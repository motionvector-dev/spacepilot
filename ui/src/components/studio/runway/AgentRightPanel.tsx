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
    <aside className="fixed right-0 top-0 bottom-0 w-[320px] bg-surface border-l border-line-200 z-30 flex flex-col pt-[44px] select-none">
      {/* Panel Header */}
      <div className="h-10 px-4 border-b border-line-200 flex items-center justify-between bg-ground/40">
        <div className="flex items-center gap-2 font-mono text-xs text-ink-900">
          <Bot className="w-4 h-4 text-agent" />
          <span className="font-bold">Director Agent Chat</span>
        </div>
        <span className="text-[10px] font-mono text-verify bg-verify-soft px-2 py-0.5 rounded border border-verify/20">
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
                  ? 'bg-strong text-ink-900 border-line-400'
                  : 'bg-agent-soft text-agent border-agent/30'
              }`}>
                {msg.role === 'user' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
              </div>
              <span className="text-xs font-semibold text-ink-700 font-sans">
                {msg.role === 'user' ? 'You' : 'AI Director'}
              </span>
              <span className="text-[10px] font-mono text-ink-300 ml-auto">
                {msg.timestamp}
              </span>
            </div>

            {/* Message Bubble */}
            <div className={`rounded-xl p-3 text-xs leading-relaxed border ${
              msg.role === 'user'
                ? 'bg-inset border-line-200 text-ink-900 font-sans'
                : 'bg-raised border-line-300 text-ink-900 space-y-2 font-sans'
            }`}>
              <p>{msg.text}</p>

              {/* Reasoning Expander Trace — model-authored reasoning, so the icon keeps the agent hue */}
              {msg.reasoning && (
                <div className="border border-line-200 rounded-lg overflow-hidden bg-ground/60 mt-2">
                  <button
                    onClick={() => toggleReasoning(msg.id)}
                    className="flex items-center justify-between w-full p-2 text-[11px] text-ink-700 hover:text-ink transition-colors bg-inset cursor-pointer"
                  >
                    <div className="flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-agent" />
                      <span className="font-mono font-medium">Model Reasoning</span>
                    </div>
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expandedReasoning[msg.id] ? 'rotate-180' : ''}`} />
                  </button>
                  {expandedReasoning[msg.id] && (
                    <div className="p-2.5 text-[10px] text-ink-700 font-mono leading-relaxed border-t border-line-200 whitespace-pre-line bg-ground/80">
                      {msg.reasoning}
                    </div>
                  )}
                </div>
              )}

              {/* Prompt Tags Breakdown */}
              {msg.tags && msg.tags.length > 0 && (
                <div className="pt-2 border-t border-line-200 space-y-1.5">
                  <div className="text-[10px] font-mono text-ink-500 uppercase tracking-wider">
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
                        className="px-2 py-0.5 rounded bg-inset hover:bg-verify-soft border border-line-200 hover:border-verify/30 text-ink-700 hover:text-verify text-[10px] font-mono transition-all cursor-pointer"
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
      <div className="p-3.5 border-t border-line-200 bg-raised space-y-3">
        <div className="flex items-center justify-between text-xs font-mono text-ink">
          <span className="font-bold flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-verify" />
            Motion Guidance
          </span>
          <span className="text-[10px] text-ink-500">Realtime</span>
        </div>

        {/* Motion Amount */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-ink-700">Motion Amount</span>
            <span className="text-verify font-bold">{motionAmount}</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={motionAmount}
            onChange={(e) => setMotionAmount(Number(e.target.value))}
            className="w-full accent-verify cursor-pointer h-1 bg-inset rounded"
          />
        </div>

        {/* Guidance Scale */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-ink-700">Guidance Scale (CFG)</span>
            <span className="text-ink-900 font-bold">{guidanceScale.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="1.0"
            max="20.0"
            step="0.5"
            value={guidanceScale}
            onChange={(e) => setGuidanceScale(Number(e.target.value))}
            className="w-full accent-ink-900 cursor-pointer h-1 bg-inset rounded"
          />
        </div>

        {/* Camera Pan Orbit */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-ink-700">Camera Orbit (Pan)</span>
            <span className="text-ink-900 font-bold">{panAngle > 0 ? `+${panAngle}°` : `${panAngle}°`}</span>
          </div>
          <input
            type="range"
            min="-45"
            max="45"
            value={panAngle}
            onChange={(e) => setPanAngle(Number(e.target.value))}
            className="w-full accent-ink-900 cursor-pointer h-1 bg-inset rounded"
          />
        </div>
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-line-200 bg-surface">
        <div className="relative flex items-center bg-raised border border-line-200 rounded-xl focus-within:border-line-300 transition-colors">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            placeholder="Tell agent to adjust scene..."
            className="w-full bg-transparent text-xs text-ink placeholder:text-ink-300 outline-none py-2.5 pl-3 pr-9 font-sans"
          />
          <button
            onClick={handleSend}
            className="absolute right-1.5 w-7 h-7 flex items-center justify-center rounded-lg text-ink-500 hover:text-ink hover:bg-inset transition-colors cursor-pointer"
            title="Send Message"
          >
            <Send className="w-3.5 h-3.5 text-verify" />
          </button>
        </div>
      </div>
    </aside>
  );
};

export default AgentRightPanel;
