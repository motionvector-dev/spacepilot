import { useState, useEffect } from 'react';
import LandingPage from './pages/LandingPage';
import StudioPage from './pages/StudioPage';
import CreatePage from './pages/CreatePage';
import CockpitPage from './pages/CockpitPage';
import DocsPage from './pages/DocsPage';
import BlueprintPage from './pages/BlueprintPage';
import OvenAdminPage from './pages/OvenAdminPage';

export default function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  if (currentPath === '/create') {
    return <CreatePage />;
  }

  if (currentPath === '/studio') {
    return <StudioPage />;
  }

  if (currentPath === '/cockpit') {
    return <CockpitPage />;
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
