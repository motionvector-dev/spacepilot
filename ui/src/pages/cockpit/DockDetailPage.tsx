/** One dock: a machine you rent, whether or not it is currently running.
 *
 * A stopped dock is asleep, not gone. The page shows the same facts either
 * way — what it would be, what it would cost — so the decision to start it is
 * made against real numbers instead of a launch button and a surprise.
 */
import { useDock } from '../../hooks/useFleet';
import {
  Empty,
  Eyebrow,
  Fact,
  Failed,
  Loading,
  Panel,
  PanelHead,
} from '../../components/cockpit/v1/atoms';
import { age } from '../../lib/fleet';

export default function DockDetailPage() {
  const dock = useDock();
  const now = Date.now();
  const d = dock.data;

  if (dock.isError) {
    return (
      <div className="mx-auto max-w-[1180px] px-5 py-8 md:px-8">
        <Panel>
          <PanelHead title="Dock" />
          <Failed error={dock.error} />
        </Panel>
      </div>
    );
  }
  if (!d) {
    return (
      <div className="mx-auto max-w-[1180px] px-5 py-8 md:px-8">
        <Panel>
          <PanelHead title="Dock" />
          <Loading what="the dock" />
        </Panel>
      </div>
    );
  }

  const rate = d.config.spot_hourly_rate;

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6 md:px-8 md:py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3 pb-6">
        <div>
          <Eyebrow>Dock · a machine you rent</Eyebrow>
          <h1 className="mt-2 mb-1 text-[28px] leading-tight font-medium tracking-[-0.02em] text-ink">
            {d.config.instance_type ?? 'no instance type configured'}
          </h1>
          <p className="m-0 font-mono text-[12px] text-ink-700">
            {d.gpu_online
              ? 'running'
              : 'asleep — it still exists, and work can wait for it'}
            {d.config.region ? ` · ${d.config.region}` : ''}
          </p>
        </div>
        <div className="font-mono text-[11px] text-ink-500">
          {age(dock.dataUpdatedAt, now)}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel>
          {/* Money first, and on its own panel, because CONCEPT.md makes spend
              a decision rather than a consequence. */}
          <PanelHead title="Money" aside={d.gpu_online ? 'clock running' : 'clock stopped'} />
          <div className="divide-y divide-line-100 px-4 pb-3 pt-1">
            <Fact
              label="Rate while running"
              value={rate !== null ? `$${rate.toFixed(2)}/hr` : null}
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
                  : 'not started'
              }
            />
            <Fact
              label="An hour from now would cost"
              value={
                rate !== null && d.estimated_cost_usd !== null
                  ? `$${(d.estimated_cost_usd + rate).toFixed(2)}`
                  : null
              }
              unknown="needs a rate and a meter"
            />
          </div>
        </Panel>

        <Panel>
          <PanelHead title="The machine" />
          <div className="divide-y divide-line-100 px-4 pb-3 pt-1">
            <Fact label="Instance type" value={d.config.instance_type} />
            <Fact label="Region" value={d.config.region} />
            <Fact label="Instance id" value={d.instance?.id ?? null} unknown="none running" />
            <Fact label="State" value={d.instance?.state ?? 'stopped'} />
            <Fact
              label="Address"
              value={d.instance?.ip ?? null}
              unknown="none running"
            />
            <Fact label="Worker reachable" value={d.gpu_online ? (d.worker_ready ? 'yes' : 'no') : 'n/a'} />
          </div>
        </Panel>

        <Panel>
          <PanelHead title="What the daemon says" />
          {d.message ? (
            <p className="m-0 px-4 py-4 text-[12px] leading-relaxed text-ink-900">
              {d.message}
            </p>
          ) : (
            <Empty>The status route returned no message.</Empty>
          )}
          {d.ssh_command ? (
            <pre className="mx-4 mb-4 overflow-x-auto rounded-2 border border-line-200 bg-inset p-3 font-mono text-[11px] text-ink-900">
              {d.ssh_command}
            </pre>
          ) : null}
          <p className="m-0 border-t border-line-100 px-4 py-4 text-[12px] leading-relaxed text-ink-500">
            Starting this box is not a button on this page yet. The route
            exists — <span className="font-mono">POST /api/gpu/launch</span>,
            token-guarded — but a control that spends{' '}
            {rate !== null ? `$${rate.toFixed(2)} an hour` : 'money'} needs the
            spend gate first, and that gate is M2. Until then this screen
            reports, and <span className="font-mono">spacepilot launch</span>{' '}
            decides.
          </p>
        </Panel>
      </div>
    </div>
  );
}
