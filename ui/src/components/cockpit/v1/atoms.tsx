/** The cockpit's small parts.
 *
 * Two of these carry rules from docs/design/CONCEPT.md rather than taste:
 * `Fact` refuses to print a value it was not given, and `Provenance` refuses
 * to show a number without saying how we know it.
 */
import type { ReactNode } from 'react';

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="font-mono text-[11px] uppercase tracking-[0.04em] text-ink-700">
      {children}
    </div>
  );
}

export function Panel({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-3 border border-line-200 bg-raised ${className}`}
    >
      {children}
    </section>
  );
}

export function PanelHead({
  title,
  aside,
}: {
  title: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <header className="flex items-baseline justify-between gap-3 border-b border-line-100 px-4 py-3">
      <Eyebrow>{title}</Eyebrow>
      {aside ? <div className="text-[11px] text-ink-500">{aside}</div> : null}
    </header>
  );
}

export type Tone = 'live' | 'asleep' | 'wrong' | 'idle';

const DOT: Record<Tone, string> = {
  live: 'bg-verify',
  asleep: 'bg-ink-500',
  wrong: 'bg-danger',
  idle: 'bg-accent',
};

export function Dot({ tone }: { tone: Tone }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-[7px] shrink-0 rounded-full ${DOT[tone]}`}
    />
  );
}

/** A labelled value. `value === null` means the backend did not report it, and
 *  that is printed as words — never as 0, "—", or an omitted row, all of which
 *  read as a measurement of nothing rather than an absence of measurement. */
export function Fact({
  label,
  value,
  unknown = 'not reported',
  mono = true,
}: {
  label: string;
  value: string | number | null | undefined;
  unknown?: string;
  mono?: boolean;
}) {
  const missing = value === null || value === undefined || value === '';
  return (
    <div className="flex items-baseline justify-between gap-4 py-[7px]">
      <span className="text-[12px] text-ink-700">{label}</span>
      <span
        className={`text-right text-[12px] ${mono ? 'font-mono' : ''} ${
          missing ? 'italic text-ink-500' : 'text-ink'
        }`}
      >
        {missing ? unknown : value}
      </span>
    </div>
  );
}

/** CONCEPT.md: every number says how we know it, and the three never blend. */
export function Provenance({ kind }: { kind: string }) {
  const known =
    kind === 'flown'
      ? { label: 'flown', cls: 'border-verify/40 text-verify' }
      : kind === 'on_paper'
        ? { label: 'on paper', cls: 'border-line-400 text-ink-700' }
        : kind === 'unflown'
          ? { label: 'unflown', cls: 'border-line-300 text-ink-500' }
          : null;
  return (
    <span
      className={`rounded-1 border px-[5px] py-px font-mono text-[10px] uppercase tracking-[0.06em] ${
        known ? known.cls : 'border-danger/40 text-danger'
      }`}
    >
      {known ? known.label : `unknown: ${kind}`}
    </span>
  );
}

/** An empty state that says why it is empty. "Nothing here" and "we never
 *  asked" look identical on screen and mean opposite things. */
export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 px-4 py-5 text-[12px] leading-relaxed text-ink-500">
      {children}
    </p>
  );
}

export function Failed({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <p className="m-0 px-4 py-5 text-[12px] leading-relaxed text-danger">
      This did not load, so nothing is shown rather than a stale or invented
      value. <span className="font-mono text-[11px]">{msg}</span>
    </p>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <p className="m-0 px-4 py-5 text-[12px] text-ink-500">Reading {what}…</p>
  );
}
