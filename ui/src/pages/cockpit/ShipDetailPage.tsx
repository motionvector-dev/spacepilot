/** One ship, in full: what it is, what it can run, and what it has actually
 *  done. The order is deliberate — verdicts before specs, measurements before
 *  claims. CONCEPT.md: readiness beats specs, evidence beats confidence.
 */
import { useState } from 'react';
import {
  useCompatibility,
  useFlown,
  useProfile,
  useRuntimes,
  useSystems,
} from '../../hooks/useFleet';
import {
  Empty,
  Eyebrow,
  Fact,
  Failed,
  Loading,
  Panel,
  PanelHead,
  Provenance,
} from '../../components/cockpit/v1/atoms';
import { age, fmtGb, matchesLiveMachine } from '../../lib/fleet';

const VERDICT_LABEL: Record<string, string> = {
  fits: 'Runs here',
  tight: 'Tight fit',
  wont_fit: 'Will not fit',
};

const VERDICT_CLASS: Record<string, string> = {
  fits: 'text-verify',
  tight: 'text-accent',
  wont_fit: 'text-ink-500',
};

export default function ShipDetailPage() {
  const profile = useProfile();
  const runtimes = useRuntimes();
  const compat = useCompatibility();
  const flownQ = useFlown();
  const systemsQ = useSystems();
  const [showAllModels, setShowAllModels] = useState(false);
  const now = Date.now();

  const p = profile.data;

  if (profile.isError) {
    return (
      <div className="mx-auto max-w-[1180px] px-5 py-8 md:px-8">
        <Panel>
          <PanelHead title="This machine" />
          <Failed error={profile.error} />
        </Panel>
      </div>
    );
  }
  if (!p) {
    return (
      <div className="mx-auto max-w-[1180px] px-5 py-8 md:px-8">
        <Panel>
          <PanelHead title="This machine" />
          <Loading what="the hardware probe" />
        </Panel>
      </div>
    );
  }

  // The corpus row for this machine, if it has ever been recorded. It is what
  // links the live probe to the flown numbers.
  const record = (systemsQ.data?.systems ?? []).find((s) =>
    matchesLiveMachine(s, p),
  );
  const flown = (flownQ.data?.summaries ?? []).filter(
    (f) => record && f.system_id === record.id,
  );

  const rows = runtimes.data?.runtimes ?? [];
  const verdicts = compat.data ? compat.data.verdicts : {};
  const models = compat.data?.models ?? [];
  const ranked = [...models].sort((a, b) => {
    const va = verdicts[a.recipe_id];
    const vb = verdicts[b.recipe_id];
    const rank = (v?: { verdict: string }) =>
      v?.verdict === 'fits' ? 0 : v?.verdict === 'tight' ? 1 : 2;
    return rank(va) - rank(vb) || a.name.localeCompare(b.name);
  });
  const shown = showAllModels ? ranked : ranked.slice(0, 12);

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6 md:px-8 md:py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3 pb-6">
        <div>
          <Eyebrow>Ship · a machine you own</Eyebrow>
          <h1 className="mt-2 mb-1 text-[28px] leading-tight font-medium tracking-[-0.02em] text-ink">
            {p.machine_name ?? p.chip}
          </h1>
          <p className="m-0 font-mono text-[12px] text-ink-700">
            {p.chip} · {p.backend_detail ?? p.backend} · {p.os_name}{' '}
            {p.os_version} · {p.arch}
          </p>
        </div>
        <div className="font-mono text-[11px] text-ink-500">
          {age(profile.dataUpdatedAt, now)}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHead title="What it has" />
            <div className="divide-y divide-line-100 px-4 pb-3 pt-1">
              <Fact label="Model" value={p.machine_model} />
              <Fact label="CPU cores" value={p.cpu_cores} />
              <Fact label="GPU cores" value={p.gpu_cores} />
              <Fact label="Memory, total" value={fmtGb(p.memory_total_bytes)} />
              <Fact label="Memory, free" value={fmtGb(p.memory_free_bytes)} />
              <Fact
                label="Ceiling for a model"
                value={fmtGb(p.memory_limit_bytes)}
              />
              {/* Where the ceiling came from matters: a number the OS reports
                  and a number we guessed are not the same kind of fact. */}
              <Fact
                label="Ceiling measured or guessed"
                value={
                  p.memory_limit_source === 'metal'
                    ? 'reported by Metal'
                    : p.memory_limit_source === 'heuristic'
                      ? 'estimated, not reported'
                      : p.memory_limit_source
                }
                mono={false}
              />
              <Fact label="Unified memory" value={p.memory_unified ? 'yes' : 'no'} />
              <Fact label="Disk free" value={fmtGb(p.disk_free_bytes)} />
              <Fact label="Weights live in" value={p.disk_path} />
            </div>
          </Panel>

          <Panel>
            <PanelHead
              title="Flown here"
              aside={record ? record.id : 'not in the corpus'}
            />
            {flownQ.isError ? (
              <Failed error={flownQ.error} />
            ) : !record ? (
              <Empty>
                This machine has no row in the measurement corpus, so no number
                on this page can be attributed to it. Running anything through
                the CLI writes one.
              </Empty>
            ) : flown.length === 0 ? (
              <Empty>
                The corpus knows this machine but has no finished runs for it
                yet. Nothing is shown, rather than a spec sheet standing in for
                a measurement.
              </Empty>
            ) : (
              <ul className="m-0 list-none space-y-2 px-4 pb-4 pt-3 p-0">
                {flown.map((f) => {
                  const solo = f.solo_median !== null;
                  const median = f.solo_median ?? f.observed_median;
                  const samples = solo ? f.solo_samples : f.observed_samples;
                  return (
                    <li
                      key={`${f.model_id}-${f.metric}`}
                      className="border-b border-line-100 pb-2 last:border-0"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-[12px] text-ink">
                          {f.model_id}
                        </span>
                        <Provenance kind={f.provenance} />
                      </div>
                      <div className="mt-1 flex items-baseline justify-between gap-2">
                        <span className="text-[11px] text-ink-700">
                          {f.metric} · {solo ? 'alone on the box' : 'sharing the box'}{' '}
                          · {samples} run{samples === 1 ? '' : 's'}
                          {f.failed_samples > 0
                            ? ` · ${f.failed_samples} failed`
                            : ''}
                        </span>
                        <span className="font-mono text-[13px] text-ink">
                          {median !== null ? median.toFixed(2) : 'no median'}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        </div>

        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHead
              title="Runtimes on this machine"
              aside={runtimes.data ? age(runtimes.dataUpdatedAt, now) : null}
            />
            {runtimes.isError ? (
              <Failed error={runtimes.error} />
            ) : rows.length === 0 ? (
              <Loading what="the runtime probe" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[12px]">
                  <thead>
                    <tr className="border-b border-line-100 text-left font-mono text-[10px] uppercase tracking-[0.06em] text-ink-500">
                      <th className="px-4 py-2 font-normal">Runtime</th>
                      <th className="px-4 py-2 font-normal">Serves</th>
                      <th className="px-4 py-2 font-normal">State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr
                        key={r.id}
                        className="border-b border-line-100 last:border-0"
                      >
                        <td className="px-4 py-[9px] align-top">
                          <span className="text-ink">{r.name}</span>
                          <span className="ml-2 font-mono text-[10px] text-ink-500">
                            {r.status.version ?? ''}
                          </span>
                        </td>
                        <td className="px-4 py-[9px] align-top font-mono text-[11px] text-ink-700">
                          {r.serves.join(', ')}
                        </td>
                        <td className="px-4 py-[9px] align-top">
                          {r.status.installed ? (
                            r.status.below_minimum ? (
                              <span className="text-accent">
                                Installed, older than the registry wants
                                {r.status.wanted_version
                                  ? ` (${r.status.wanted_version})`
                                  : ''}
                              </span>
                            ) : (
                              <span className="text-verify">Ready</span>
                            )
                          ) : r.usable_here ? (
                            <span className="text-ink-700">
                              Not installed — this silicon could run it
                            </span>
                          ) : (
                            <span className="text-ink-500">
                              Not for this machine ({r.backends.join('/')})
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHead
              title="Models, judged against this machine"
              aside={
                compat.data
                  ? `${ranked.length} in the registry`
                  : null
              }
            />
            {compat.isError ? (
              <Failed error={compat.error} />
            ) : !compat.data ? (
              <Loading what="model verdicts" />
            ) : (
              <>
                <ul className="m-0 list-none p-0">
                  {shown.map((m) => {
                    const v = verdicts[m.recipe_id];
                    return (
                      <li
                        key={m.recipe_id}
                        className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line-100 px-4 py-[9px] last:border-0"
                      >
                        <span className="min-w-0 flex-1 truncate text-[12px] text-ink">
                          {m.name}
                          <span className="ml-2 font-mono text-[10px] text-ink-500">
                            {m.kind}
                            {m.params ? ` · ${m.params}` : ''}
                            {m.quantization ? ` · ${m.quantization}` : ''}
                          </span>
                        </span>
                        <span
                          className={`text-[12px] ${
                            VERDICT_CLASS[v?.verdict ?? ''] ?? 'text-ink-500'
                          }`}
                        >
                          {VERDICT_LABEL[v?.verdict ?? ''] ??
                            (v ? v.verdict : 'no verdict')}
                        </span>
                        <span className="w-full font-mono text-[10px] text-ink-500 sm:w-auto sm:basis-full">
                          {v?.reason ?? 'the registry returned no reason'}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                {ranked.length > shown.length || showAllModels ? (
                  <button
                    type="button"
                    onClick={() => setShowAllModels((s) => !s)}
                    className="w-full cursor-pointer border-0 border-t border-line-100 bg-transparent
                               px-4 py-[10px] text-left text-[12px] text-ink-700
                               transition-colors duration-[120ms] ease-out hover:bg-raised-hover hover:text-ink"
                  >
                    {showAllModels
                      ? 'Show fewer'
                      : `Show all ${ranked.length}`}
                  </button>
                ) : null}
              </>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
