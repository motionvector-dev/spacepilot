
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
    p0: 'bg-strong text-ink border border-line-500 font-bold',
    p1: 'bg-inset text-ink border border-line-400',
    p2: 'bg-inset text-ink border border-line-400',
    done: 'bg-verify-soft text-verify border border-verify/30',
  }[priority];

  return (
    <div
      className="bg-inset border border-line-200 rounded-xl p-3.5 flex flex-col gap-2.5 transition-all duration-200 cursor-grab hover:bg-strong hover:border-line-400 hover:-translate-y-0.5 relative group"
      style={borderColor ? { borderColor } : {}}
    >
      <span className={`self-start font-mono text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${badgeClasses}`}>
        {badgeText}
      </span>
      <div className="text-[13.5px] font-bold text-ink leading-snug">
        {title}
      </div>
      <div className="text-xs text-ink-700 leading-relaxed">
        {description}
      </div>
      <div className="flex items-center justify-between font-mono text-[10px] text-ink-500 border-t border-line-200 pt-2 mt-0.5">
        <span className="flex items-center gap-1 text-ink-700">
          {persona}
        </span>
        <span style={statusColor ? { color: statusColor } : {}}>
          {status}
        </span>
      </div>
    </div>
  );
}
