import { useState, useEffect } from 'react';
import StudioPage from './pages/StudioPage';
import CreatePage from './pages/CreatePage';
import CockpitPage from './pages/CockpitPage';
import DocsPage from './pages/DocsPage';
import BlueprintPage from './pages/BlueprintPage';
import OvenAdminPage from './pages/OvenAdminPage';

function Home() {
  return (
    <div className="min-h-screen bg-black text-[#fafafa] font-sans flex items-center justify-center">
      <div className="text-center">
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-[#71717a] mb-6">SpacePilot Runtime · Internal</p>
        <nav className="flex gap-6 text-sm text-[#a1a1aa]">
          <a href="/create" className="hover:text-white transition-colors">/create</a>
          <a href="/studio" className="hover:text-white transition-colors">/studio</a>
          <a href="/cockpit" className="hover:text-white transition-colors">/cockpit</a>
          <a href="/docs" className="hover:text-white transition-colors">/docs</a>
        </nav>
      </div>
    </div>
  );
}

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

  return <Home />;
}
