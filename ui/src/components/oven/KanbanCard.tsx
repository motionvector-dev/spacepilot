
interface KanbanCardProps {
  priority: 'p0' | 'p1' | 'p2' | 'done';
  badgeText: string;
  title: string;
  description: string;
  persona: string;
  status: string;
  statusColor?: string;
  borderColor?: string;
}

export function KanbanCard({ priority, badgeText, title, description, persona, status, statusColor, borderColor }: KanbanCardProps) {
  const badgeClasses = {
    p0: 'bg-rose-500/15 text-rose-500 border border-rose-500/30',
    p1: 'bg-amber-500/15 text-amber-500 border border-amber-500/30',
    p2: 'bg-blue-500/15 text-blue-500 border border-blue-500/30',
    done: 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30',
  }[priority];

  return (
    <div 
      className="bg-white/5 border border-white/10 rounded-xl p-3.5 flex flex-col gap-2.5 transition-all duration-200 cursor-grab hover:bg-[#1c2030]/95 hover:border-white/20 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(0,0,0,0.3)] relative group"
      style={borderColor ? { borderColor } : {}}
    >
      <span className={`self-start font-mono text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${badgeClasses}`}>
        {badgeText}
      </span>
      <div className="text-[13.5px] font-bold text-slate-50 leading-snug">
        {title}
      </div>
      <div className="text-xs text-slate-400 leading-relaxed">
        {description}
      </div>
      <div className="flex items-center justify-between font-mono text-[10px] text-slate-500 border-t border-white/5 pt-2 mt-0.5">
        <span className="flex items-center gap-1 text-cyan-500">
          {persona}
        </span>
        <span style={statusColor ? { color: statusColor } : {}}>
          {status}
        </span>
      </div>
    </div>
  );
}
