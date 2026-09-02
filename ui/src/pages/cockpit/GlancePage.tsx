/** Glance — the screen the cockpit opens on.
 *
 * One question: what can run right now, and what is it costing. Ships first,
 * because the machine you already own is the free answer and the shipped
 * cockpit's mistake was opening on a rented box that does not exist.
 *
 * Every value below comes from a route in spacepilot/api/routes/. Nothing is
 * a placeholder, a default, or a plausible-looking constant.
 */
import { useGlance } from '../../hooks/useFleet';
import type { Route } from '../../components/cockpit/v1/CockpitShell';
import {
  Dot,
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

export default function GlancePage({
  onNavigate,
}: {
  onNavigate: (r: Route) => void;
}) {
  const g = useGlance();
  const now = Date.now();

  if (g.allFailed) {
    return (
      <div className="mx-auto max-w-[1180px] px-5 py-10 md:px-8">
        <h1 className="m-0 text-[20px] font-medium text-ink">
          The daemon is not answering.
        </h1>
        <p className="mt-3 max-w-[60ch] text-[13px] leading-relaxed text-ink-700">
          Nothing on this page is shown, because every value it would show comes
          from a route on <span className="font-mono">127.0.0.1:8088</span> and
          none of them replied. An empty cockpit is the honest picture here; a
          cockpit full of zeroes would be a lie about a machine we cannot see.
        </p>
        <pre className="mt-5 overflow-x-auto rounded-3 border border-line-200 bg-raised p-4 font-mono text-[12px] text-ink-900">
          spacepilot serve --host 127.0.0.1 --port 8088
        </pre>
      </div>
    );
  }

  const p = g.profile.data;
  const d = g.dock.data;
  const rt = g.runtimes.data;
  const compat = g.compat.data;
  const flown = g.flown.data?.summaries ?? [];
  const systems = g.systems.data?.systems ?? [];

  const installed = rt?.runtimes.filter((r) => r.status.installed) ?? [];
  const stale = installed.filter((r) => r.status.below_minimum);
  const usableNotInstalled =
    rt?.runtimes.filter((r) => r.usable_here && !r.status.installed) ?? [];

  const verdicts = compat ? Object.values(compat.verdicts) : [];
  const fits = verdicts.filter((v) => v.verdict === 'fits').length;
  const runnableNow = verdicts.filter((v) => v.runnable_now).length;

  // Systems the corpus knows that are not the machine in front of us. They are
  // ships too — asleep, elsewhere, or retired — and hiding them would make the
  // fleet look like one box.
  const elsewhere = systems.filter((s) => !matchesLiveMachine(s, p));

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6 md:px-8 md:py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3 pb-6">
        <div>
          <Eyebrow>Right now</Eyebrow>
          <h1 className="mt-2 mb-0 text-[28px] leading-tight font-medium tracking-[-0.02em] text-ink">
            What can run, and what it costs.
          </h1>
        </div>
        <div className="font-mono text-[11px] text-ink-500">
          {age(g.oldestUpdate, now)}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* ---------------------------------------------------------- ships */}
        <Panel>
          <PanelHead
            title="Ships · machines you own"
            aside={p ? age(g.profile.dataUpdatedAt, now) : null}
          />
          {g.profile.isError ? (
            <Failed error={g.profile.error} />
          ) : !p ? (
            <Loading what="this machine" />
          ) : (
            <div className="px-4 pb-3">
              <button
                type="button"
                onClick={() => onNavigate({ name: 'ship', id: 'local' })}
                className="-mx-2 mt-3 flex w-[calc(100%+1rem)] cursor-pointer items-center gap-2 rounded-2
                           border-0 bg-transparent px-2 py-2 text-left transition-colors duration-[120ms]
                           ease-out hover:bg-raised-hover"
              >
                <Dot tone="live" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] text-ink">
                    {p.machine_name ?? p.chip}
                  </span>
                  <span className="block truncate font-mono text-[11px] text-ink-700">
                    {p.chip} · {p.backend_detail ?? p.backend}
                  </span>
                </span>
              </button>
              <div className="divide-y divide-line-100 border-t border-line-100 pt-1">
                <Fact
                  label="Memory a model may use"
                  value={fmtGb(p.memory_limit_bytes)}
                />
                <Fact label="Free right now" value={fmtGb(p.memory_free_bytes)} />
                <Fact label="Disk for weights" value={fmtGb(p.disk_free_bytes)} />
                <Fact
                  label="Ships known elsewhere"
                  value={
                    g.systems.isError
                      ? null
                      : elsewhere.length === 0
                        ? 'none'
                        : `${elsewhere.length}, none here now`
                  }
                  unknown="the corpus did not load"
                />
              </div>
            </div>
          )}
        </Panel>

        {/* ---------------------------------------------------------- docks */}
        <Panel>
          <PanelHead
            title="Docks · machines you rent"
            aside={d ? age(g.dock.dataUpdatedAt, now) : null}
          />
          {g.dock.isError ? (
            <Failed error={g.dock.error} />
          ) : !d ? (
            <Loading what="the dock" />
          ) : (
            <div className="px-4 pb-3">
              <button
                type="button"
                onClick={() => onNavigate({ name: 'dock', id: 'aws' })}
                className="-mx-2 mt-3 flex w-[calc(100%+1rem)] cursor-pointer items-center gap-2 rounded-2
                           border-0 bg-transparent px-2 py-2 text-left transition-colors duration-[120ms]
                           ease-out hover:bg-raised-hover"
              >
                <Dot tone={d.gpu_online ? 'live' : 'asleep'} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] text-ink">
                    {d.config.instance_type ?? 'no instance type configured'}
                  </span>
                  <span className="block truncate font-mono text-[11px] text-ink-700">
                    {d.gpu_online
                      ? 'running'
                      : 'asleep — work can wait for it'}{' '}
                    · {d.config.region ?? 'no region'}
                  </span>
                </span>
              </button>
              <div className="divide-y divide-line-100 border-t border-line-100 pt-1">
                {/* Money is loud: the rate is on screen whether or not the box
                    is running, so renting is never a silent default. */}
                <Fact
                  label="Rate while running"
                  value={
                    d.config.spot_hourly_rate !== null
                      ? `$${d.config.spot_hourly_rate.toFixed(2)}/hr`
                      : null
                  }
                  unknown="no rate configured"
                />
                <Fact
                  label="Accrued this session"
                  value={
                    d.estimated_cost_usd !== null
                      ? `$${d.estimated_cost_usd.toFixed(2)}`
                      : null
                  }
                />
                <Fact
                  label="Running for"
                  value={
                    d.gpu_online && d.uptime_minutes !== null
                      ? `${d.uptime_minutes.toFixed(0)} min`
                      : d.gpu_online
                        ? null
                        : 'not started'
                  }
                />
                <Fact
                  label="Worker reachable"
                  value={d.gpu_online ? (d.worker_ready ? 'yes' : 'no') : 'n/a'}
                />
              </div>
            </div>
          )}
        </Panel>

        {/* ------------------------------------------------------ providers */}
        <Panel>
          <PanelHead title="Providers · managed APIs" />
          <Empty>
            SpacePilot has no provider inventory yet. There is no route under{' '}
            <span className="font-mono text-ink-700">
              spacepilot/api/routes/
            </span>{' '}
            that returns one, so this panel shows nothing rather than a count of
            zero — those mean different things, and only one of them is true
            here.
            <br />
            <br />
            The credentials exist in Doppler; what is missing is the endpoint
            that reports which of them are live and what they charge. That is
            M3 in <span className="font-mono text-ink-700">COCKPIT.md</span>.
          </Empty>
        </Panel>
      </div>

      {/* ------------------------------------------------------- readiness */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel>
          <PanelHead
            title="Runtimes"
            aside={rt ? age(g.runtimes.dataUpdatedAt, now) : null}
          />
          {g.runtimes.isError ? (
            <Failed error={g.runtimes.error} />
          ) : !rt ? (
            <Loading what="runtimes" />
          ) : (
            <div className="px-4 pb-3 pt-1 divide-y divide-line-100">
              <Fact
                label="Installed here"
                value={`${installed.length} of ${rt.runtimes.length}`}
              />
              <Fact
                label="Older than the registry wants"
                value={stale.length === 0 ? 'none' : String(stale.length)}
              />
              <Fact
                label="This silicon could run, not installed"
                value={
                  usableNotInstalled.length === 0
                    ? 'none'
                    : String(usableNotInstalled.length)
                }
              />
              <Fact label="Interpreter" value={rt.interpreter} mono />
            </div>
          )}
        </Panel>

        <Panel>
          <PanelHead
            title="Models"
            aside={compat ? age(g.compat.dataUpdatedAt, now) : null}
          />
          {g.compat.isError ? (
            <Failed error={g.compat.error} />
          ) : !compat ? (
            <Loading what="model verdicts" />
          ) : (
            <div className="px-4 pb-3 pt-1 divide-y divide-line-100">
              <Fact
                label="Fit in this machine's memory"
                value={`${fits} of ${compat.models.length}`}
              />
              <Fact
                label="Could start without downloading"
                value={`${runnableNow} of ${compat.models.length}`}
              />
              <Fact
                label="Weights already on disk"
                value={String(compat.installed.length)}
              />
              <Fact label="Best fit here" value={compat.recommended} />
            </div>
          )}
        </Panel>

        <Panel>
          <PanelHead title="Flown" aside="measured here, never estimated" />
          {g.flown.isError ? (
            <Failed error={g.flown.error} />
          ) : !g.flown.data ? (
            <Loading what="measurements" />
          ) : flown.length === 0 ? (
            <Empty>
              Nothing has been measured on any machine yet. This stays empty
              until a real run finishes — it will never fill up with a spec
              sheet.
            </Empty>
          ) : (
            <div className="px-4 pb-3 pt-2">
              <ul className="m-0 list-none space-y-[6px] p-0">
                {flown.slice(0, 4).map((f) => {
                  const median = f.solo_median ?? f.observed_median;
                  return (
                    <li
                      key={`${f.system_id}-${f.model_id}-${f.metric}`}
                      className="flex items-baseline justify-between gap-3"
                    >
                      <span className="min-w-0 flex-1 truncate text-[12px] text-ink-900">
                        {f.model_id}{' '}
                        <span className="text-ink-500">{f.metric}</span>
                      </span>
                      <span className="font-mono text-[12px] text-ink">
                        {median !== null ? median.toFixed(2) : '—'}
                      </span>
                      <Provenance kind={f.provenance} />
                    </li>
                  );
                })}
              </ul>
              <p className="mt-3 mb-0 text-[11px] leading-relaxed text-ink-500">
                {flown.length} measurement{flown.length === 1 ? '' : 's'} in the
                corpus. A median marked solo ran alone on the box; an observed
                one shared it. The two never merge into a single number.
              </p>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
