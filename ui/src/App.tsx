import { useState, useEffect } from 'react';
import { ThemeSwitcher } from './components/ThemeSwitcher';
import LandingPage from './pages/LandingPage';
import StudioPage from './pages/StudioPage';
import CreatePage from './pages/CreatePage';
import CockpitPage from './pages/CockpitPage';
import CockpitV1Page from './pages/CockpitV1Page';
import DocsPage from './pages/DocsPage';
import BlueprintPage from './pages/BlueprintPage';
import OvenAdminPage from './pages/OvenAdminPage';

function page(currentPath: string) {
  if (currentPath === '/create') {
    return <CreatePage />;
  }

  if (currentPath === '/studio') {
    return <StudioPage />;
  }

  // /cockpit is the v1 information architecture (docs/design/COCKPIT.md).
  // The pre-v1 tabbed screen stays reachable at /cockpit/legacy while the
  // spend gate and the SSH terminal it owns are ported across.
  if (currentPath === '/cockpit/legacy') {
    return <CockpitPage />;
  }

  if (currentPath === '/cockpit' || currentPath.startsWith('/cockpit/')) {
    return <CockpitV1Page />;
  }

  if (currentPath === '/docs') {
    return <DocsPage />;
  }

  if (currentPath === '/blueprint') {
    return <BlueprintPage />;
  }

  if (currentPath === '/admin/oven' || currentPath === '/oven') {
    return <OvenAdminPage />;
  }

  return <LandingPage />;
}

export default function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // The cockpit carries the theme control in its own rail, so the floating one
  // is suppressed there rather than shown twice.
  const ownsToggle = currentPath.startsWith('/cockpit');

  return (
    <>
      {page(currentPath)}
      {ownsToggle ? null : <ThemeSwitcher />}
    </>
  );
}
