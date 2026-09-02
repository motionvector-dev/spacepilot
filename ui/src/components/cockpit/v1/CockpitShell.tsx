/** The cockpit shell: a rail of real machines, and one screen beside it.
 *
 * The rail's top half is not a menu. Each row is a machine that exists — this
 * Mac, the AWS dock — carrying its own live state dot, so the fleet is legible
 * without navigating anywhere. The bottom half is the small flat set of tools.
 * See docs/design/COCKPIT.md for why this shape won over the other two.
 */
import type { ReactNode } from 'react';
import { ThemeSwitcher } from '../../ThemeSwitcher';
import { Dot, type Tone } from './atoms';
import { useDock, useProfile } from '../../../hooks/useFleet';
import { age } from '../../../lib/fleet';

export type Route =
  | { name: 'glance' }
  | { name: 'ship'; id: string }
  | { name: 'dock'; id: string }
  | { name: 'runtimes' }
  | { name: 'models' }
  | { name: 'settings' };

export function routeFromPath(path: string): Route {
  const rest = path.replace(/^\/cockpit\/?/, '').replace(/\/$/, '');
  if (rest === '' || rest === 'glance') return { name: 'glance' };
  if (rest.startsWith('ship/')) return { name: 'ship', id: rest.slice(5) };
  if (rest.startsWith('dock/')) return { name: 'dock', id: rest.slice(5) };
  if (rest === 'runtimes') return { name: 'runtimes' };
  if (rest === 'models') return { name: 'models' };
  if (rest === 'settings') return { name: 'settings' };
  return { name: 'glance' };
}

export function pathFor(r: Route): string {
  switch (r.name) {
    case 'glance':
      return '/cockpit';
    case 'ship':
      return `/cockpit/ship/${r.id}`;
    case 'dock':
      return `/cockpit/dock/${r.id}`;
    default:
      return `/cockpit/${r.name}`;
  }
}

function sameRoute(a: Route, b: Route) {
  return pathFor(a) === pathFor(b);
}

function RailLink({
  to,
  current,
  onNavigate,
  tone,
  label,
  detail,
}: {
  to: Route;
  current: Route;
  onNavigate: (r: Route) => void;
  tone?: Tone;
  label: string;
  detail?: string | null;
}) {
  const active = sameRoute(to, current);
  return (
    <a
      href={pathFor(to)}
      aria-current={active ? 'page' : undefined}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        onNavigate(to);
      }}
      className={`group flex items-center gap-[9px] rounded-2 px-2 py-[7px] text-[12px] no-underline
        transition-colors duration-[120ms] ease-out
        ${
          active
            ? 'bg-strong text-ink'
            : 'text-ink-900 hover:bg-raised-hover hover:text-ink'
        }`}
    >
      {tone ? <Dot tone={tone} /> : <span className="w-[7px]" aria-hidden />}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {detail ? (
        <span className="shrink-0 font-mono text-[10px] text-ink-500">
          {detail}
        </span>
      ) : null}
    </a>
  );
}

function RailGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="px-2 py-2">
      <div className="px-2 pb-[6px] font-mono text-[10px] uppercase tracking-[0.06em] text-ink-500">
        {title}
      </div>
      <div className="flex flex-col gap-px">{children}</div>
    </div>
  );
}

export function CockpitShell({
  route,
  onNavigate,
  children,
}: {
  route: Route;
  onNavigate: (r: Route) => void;
  children: ReactNode;
}) {
  const profile = useProfile();
  const dock = useDock();
  const now = Date.now();

  const shipName =
    profile.data?.machine_name || profile.data?.chip || 'this machine';
  const shipTone: Tone = profile.isError
    ? 'wrong'
    : profile.data
      ? 'live'
      : 'idle';

  const d = dock.data;
  const dockName = d?.config?.instance_type ?? 'dock';
  // "Asleep, not gone." A configured box that is not running has not vanished;
  // it is a machine that work can wait for, and the rail says so.
  const dockTone: Tone = dock.isError
    ? 'wrong'
    : d?.gpu_online
      ? 'live'
      : 'asleep';
  const dockDetail = d
    ? d.gpu_online
      ? d.estimated_cost_usd !== null
        ? `$${d.estimated_cost_usd.toFixed(2)}`
        : 'running'
      : 'asleep'
    : null;

  return (
    <div className="flex min-h-screen bg-ground text-ink-900">
      <a
        href="#cockpit-main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50
                   focus:rounded-2 focus:bg-ink focus:px-3 focus:py-2 focus:text-[12px] focus:text-ground"
      >
        Skip to content
      </a>

      <nav
        aria-label="Fleet"
        className="sticky top-0 hidden h-screen w-[228px] shrink-0 flex-col
                   border-r border-line-200 bg-surface md:flex"
      >
        <div className="flex h-[52px] items-center gap-2 border-b border-line-200 px-4">
          <Dot tone={profile.isError && dock.isError ? 'wrong' : 'live'} />
          <span className="font-mono text-[12px] uppercase tracking-[0.08em] text-ink">
            SpacePilot
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto py-1">
          <RailGroup title="Right now">
            <RailLink
              to={{ name: 'glance' }}
              current={route}
              onNavigate={onNavigate}
              label="Glance"
            />
          </RailGroup>

          <RailGroup title="Ships">
            <RailLink
              to={{ name: 'ship', id: 'local' }}
              current={route}
              onNavigate={onNavigate}
              tone={shipTone}
              label={shipName}
              detail={profile.data?.backend ?? null}
            />
          </RailGroup>

          <RailGroup title="Docks">
            <RailLink
              to={{ name: 'dock', id: 'aws' }}
              current={route}
              onNavigate={onNavigate}
              tone={dockTone}
              label={dockName}
              detail={dockDetail}
            />
          </RailGroup>

          <RailGroup title="Work">
            <RailLink
              to={{ name: 'runtimes' }}
              current={route}
              onNavigate={onNavigate}
              label="Runtimes"
            />
            <RailLink
              to={{ name: 'models' }}
              current={route}
              onNavigate={onNavigate}
              label="Models"
            />
            <RailLink
              to={{ name: 'settings' }}
              current={route}
              onNavigate={onNavigate}
              label="Settings"
            />
          </RailGroup>
        </div>

        <div className="border-t border-line-200 p-3">
          <div className="pb-2 font-mono text-[10px] text-ink-500">
            {age(
              Math.min(
                profile.dataUpdatedAt || now,
                dock.dataUpdatedAt || now,
              ),
              now,
            )}
          </div>
          <ThemeSwitcher inline />
        </div>
      </nav>

      <main id="cockpit-main" className="min-w-0 flex-1">
        {/* The rail is a screen-width luxury. Below md it collapses to a
            horizontal strip so the fleet is still the first thing visible. */}
        <div className="sticky top-0 z-10 flex items-center gap-2 overflow-x-auto border-b border-line-200 bg-surface px-3 py-2 md:hidden">
          <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink">
            SpacePilot
          </span>
          <span className="flex items-center gap-1 rounded-2 border border-line-200 px-2 py-1 text-[11px] whitespace-nowrap">
            <Dot tone={shipTone} />
            {shipName}
          </span>
          <span className="flex items-center gap-1 rounded-2 border border-line-200 px-2 py-1 text-[11px] whitespace-nowrap">
            <Dot tone={dockTone} />
            {dockName}
          </span>
        </div>
        {children}
      </main>
    </div>
  );
}
