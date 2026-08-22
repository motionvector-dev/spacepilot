import { useState } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, Check, Plus, X } from 'lucide-react';
import { useInstall, usePreview, useRuntimes, type Runtime } from '../../hooks/useRuntimes';

/* Installing a runtime is a structured operation, so it gets a structured
 * surface. A terminal would flatten "this downgrades opencv" into a line you
 * scroll past; here it is a row you have to answer. */

type State = 'installed' | 'outdated' | 'available' | 'unusable';

function stateOf(r: Runtime): State {
  if (!r.status.python_compatible || !r.usable_here) return 'unusable';
  if (r.status.below_minimum) return 'outdated';
  if (r.status.installed) return 'installed';
  return 'available';
}

const DOT: Record<State, string> = {
  installed: 'bg-verify',
  outdated: 'bg-ink-500 ring-2 ring-ink-500 ring-offset-2 ring-offset-raised',
  available: 'bg-transparent border border-ink-300',
  unusable: 'bg-transparent border border-dashed border-ink-300',
};

const LABEL: Record<State, string> = {
  installed: 'Installed',
  outdated: 'Outdated',
  available: 'Not installed',
  unusable: 'Not usable here',
};

export function RuntimeManager() {
  const { data, isLoading, error } = useRuntimes();
  const { previews, preview, clearPreview } = usePreview();
  const { job, start, reset } = useInstall();
  const [confirming, setConfirming] = useState<string | null>(null);

  if (isLoading) {
    return (
      <section className="rounded-xl border border-line-200 bg-raised p-6">
        <div className="flex items-center gap-3 text-ink-700">
          <span className="sp-spinner" /> Reading what is installed
        </div>
      </section>
    );
  }
  if (error || !data) {
    return (
      <section className="rounded-xl border border-danger bg-danger-soft p-6 text-ink">
        Could not read the runtime list. {String(error)}
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-line-200 bg-raised p-6 flex flex-col gap-5">
      <header className="flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.04em] text-ink-500 mb-1">
            Runtimes
          </p>
          <h2 className="text-xl font-medium text-ink">What can execute a model</h2>
        </div>
        <p className="font-mono text-[11px] text-ink-500 text-right">
          {data.chip || 'this machine'} · {data.backend || 'no backend'}
          <br />
          <span className="text-ink-300">{data.interpreter}</span>
        </p>
      </header>

      <p className="text-sm text-ink-700 max-w-[62ch]">
        Weights are half of it. A model needs something to run it, and that is a package
        in the interpreter above — not a download. Installing one is checked by importing
        it afterwards, because a package manager exiting cleanly does not prove much.
      </p>

      <ul className="flex flex-col divide-y divide-line-100">
        {data.runtimes.map((r) => {
          const state = stateOf(r);
          const impact = previews[r.id];
          const busy = job?.runtime_id === r.id && ['pending', 'resolving', 'installing'].includes(job.status);
          const settled = job?.runtime_id === r.id && ['completed', 'failed', 'refused'].includes(job.status);

          return (
            <li key={r.id} className="py-4 flex flex-col gap-3">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${DOT[state]}`} />
                    <span className="font-medium text-ink">{r.name}</span>
                    <span className="font-mono text-[11px] text-ink-500">
                      {LABEL[state]}{r.status.version ? ` · ${r.status.version}` : ''}
                    </span>
                  </div>
                  <p className="text-[13px] text-ink-700 mt-1 max-w-[58ch] leading-snug">{r.summary}</p>
                  <p className="font-mono text-[11px] text-ink-500 mt-1">
                    {r.serves.join(', ')} · {r.backends.join(', ')} · {r.license}
                  </p>
                  {state === 'unusable' && (
                    <p className="font-mono text-[11px] text-ink-500 mt-1">
                      {r.status.python_note || `needs ${r.backends.join(' or ')}; this machine runs ${data.backend}`}
                    </p>
                  )}
                  {state === 'outdated' && (
                    <p className="font-mono text-[11px] text-ink-900 mt-1">{r.status.reason}</p>
                  )}
                </div>

                <div className="shrink-0">
                  {state === 'available' || state === 'outdated' ? (
                    <button
                      className="sp-btn sm"
                      disabled={busy}
                      onClick={() => { reset(); setConfirming(null); preview(r.id); }}
                    >
                      {busy ? job?.status : state === 'outdated' ? 'Update' : 'Install'}
                    </button>
                  ) : state === 'installed' ? (
                    <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-verify">
                      <Check className="w-3.5 h-3.5" /> ready
                    </span>
                  ) : null}
                </div>
              </div>

              {impact === 'loading' && (
                <div className="flex items-center gap-3 text-[13px] text-ink-700 rounded-lg bg-inset px-4 py-3">
                  <span className="sp-spinner" /> Resolving what this would change
                </div>
              )}

              {impact && impact !== 'loading' && !busy && !settled && (
                <ImpactPanel
                  impact={impact}
                  confirming={confirming === r.id}
                  onCancel={() => { clearPreview(r.id); setConfirming(null); }}
                  onConfirm={() => {
                    if (impact.is_disruptive && confirming !== r.id) { setConfirming(r.id); return; }
                    clearPreview(r.id);
                    setConfirming(null);
                    start(r.id, impact.is_disruptive);
                  }}
                />
              )}

              {(busy || settled) && job && job.runtime_id === r.id && (
                <JobPanel status={job.status} message={job.message} error={job.error} onDismiss={reset} />
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function ImpactPanel({
  impact, confirming, onCancel, onConfirm,
}: {
  impact: import('../../hooks/useRuntimes').Impact;
  confirming: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (impact.error) {
    return (
      <div className="rounded-lg border border-danger bg-danger-soft px-4 py-3 text-[13px] text-ink">
        Could not resolve this install. {impact.error}
        <button className="sp-btn quiet sm ml-3" onClick={onCancel}>Close</button>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-inset border border-line-200 px-4 py-3 flex flex-col gap-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.04em] text-ink-500">
        What this changes
      </p>

      <ul className="flex flex-col gap-1 font-mono text-[12px]">
        {impact.new.map(([name, ver]) => (
          <li key={name} className="flex items-center gap-2 text-ink-700">
            <Plus className="w-3 h-3 shrink-0" />
            <span className="text-ink">{name}</span> {ver}
          </li>
        ))}
        {impact.upgrades.map(([name, from, to]) => (
          <li key={name} className="flex items-center gap-2 text-ink-700">
            <ArrowUp className="w-3 h-3 shrink-0" />
            <span className="text-ink">{name}</span> {from} → {to}
          </li>
        ))}
        {impact.downgrades.map(([name, from, to]) => (
          <li key={name} className="flex items-center gap-2 text-ink">
            <ArrowDown className="w-3 h-3 shrink-0 text-danger" />
            <span className="font-medium">{name}</span> {from} → {to}
          </li>
        ))}
      </ul>

      {impact.is_disruptive && (
        <div className="flex gap-2 items-start text-[13px] text-ink border-l-2 border-danger pl-3">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-danger" />
          <p className="leading-snug">
            This lowers a package version. Anything else in this environment that needed the
            newer one will break — later, somewhere else, with nothing pointing back here.
            A separate environment for this runtime avoids it.
          </p>
        </div>
      )}

      <div className="flex gap-2 justify-end">
        <button className="sp-btn quiet sm" onClick={onCancel}>Cancel</button>
        <button
          className={impact.is_disruptive ? 'sp-btn danger sm' : 'sp-btn sm'}
          onClick={onConfirm}
        >
          {impact.is_disruptive
            ? (confirming ? 'Yes, downgrade it' : 'Install anyway')
            : 'Install'}
        </button>
      </div>
    </div>
  );
}

function JobPanel({
  status, message, error, onDismiss,
}: { status: string; message: string | null; error: string | null; onDismiss: () => void }) {
  const done = status === 'completed';
  const refused = status === 'refused';
  const failed = status === 'failed';

  return (
    <div
      className={`rounded-lg px-4 py-3 text-[13px] flex items-start gap-3 border ${
        failed ? 'border-danger bg-danger-soft'
        : refused ? 'border-line-300 bg-inset'
        : done ? 'border-verify/40 bg-verify-soft'
        : 'border-line-200 bg-inset'
      }`}
    >
      {done ? <Check className="w-4 h-4 shrink-0 mt-0.5 text-verify" />
        : failed ? <X className="w-4 h-4 shrink-0 mt-0.5 text-danger" />
        : refused ? <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-ink-500" />
        : <span className="sp-spinner mt-0.5" />}

      <div className="min-w-0 flex-1">
        <p className="text-ink">
          {done ? message
            : refused ? 'Not installed — nothing was changed.'
            : failed ? 'The install did not take.'
            : message || status}
        </p>
        {(error && (refused || failed)) && (
          <p className="font-mono text-[11px] text-ink-700 mt-1 break-words">{error}</p>
        )}
      </div>

      {(done || refused || failed) && (
        <button className="sp-btn quiet sm" onClick={onDismiss}>Dismiss</button>
      )}
    </div>
  );
}
