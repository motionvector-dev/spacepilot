/** /cockpit — the shell, and whichever screen the rail is pointing at.
 *
 * Routing is the same pushState pattern App.tsx already uses; the app has no
 * router and adding one for six paths would be the larger change.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  CockpitShell,
  pathFor,
  routeFromPath,
  type Route,
} from '../components/cockpit/v1/CockpitShell';
import GlancePage from './cockpit/GlancePage';
import ShipDetailPage from './cockpit/ShipDetailPage';
import DockDetailPage from './cockpit/DockDetailPage';
import { RuntimeManager } from '../components/cockpit/RuntimeManager';
import { Eyebrow, Panel, PanelHead, Empty } from '../components/cockpit/v1/atoms';

function NotBuilt({ title, body }: { title: string; body: string }) {
  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6 md:px-8 md:py-8">
      <Eyebrow>{title}</Eyebrow>
      <div className="mt-4">
        <Panel>
          <PanelHead title="Not built yet" />
          <Empty>{body}</Empty>
        </Panel>
      </div>
    </div>
  );
}

export default function CockpitV1Page() {
  const [route, setRoute] = useState<Route>(() =>
    routeFromPath(window.location.pathname),
  );

  useEffect(() => {
    const onPop = () => setRoute(routeFromPath(window.location.pathname));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = useCallback((r: Route) => {
    window.history.pushState({}, '', pathFor(r));
    setRoute(r);
  }, []);

  let screen;
  switch (route.name) {
    case 'ship':
      screen = <ShipDetailPage />;
      break;
    case 'dock':
      screen = <DockDetailPage />;
      break;
    case 'runtimes':
      screen = (
        <div className="mx-auto max-w-[1180px] px-5 py-6 md:px-8 md:py-8">
          <RuntimeManager />
        </div>
      );
      break;
    case 'models':
      screen = (
        <NotBuilt
          title="Models"
          body="The verdicts are real and already on the ship screen — every model in the registry, judged against this machine's memory. What is missing here is the hub that groups them by task and starts a download, which is M2. Rather than a page of the same table under a different heading, this is empty and says so."
        />
      );
      break;
    case 'settings':
      screen = (
        <NotBuilt
          title="Settings"
          body="The daemon exposes GET and POST /api/cockpit/config, and the POST is token-guarded. Wiring an editor to it before the token flow is designed would mean a settings page that silently fails to save. That is M2."
        />
      );
      break;
    default:
      screen = <GlancePage onNavigate={navigate} />;
  }

  return (
    <CockpitShell route={route} onNavigate={navigate}>
      {screen}
    </CockpitShell>
  );
}
