import { useEffect, useState } from 'react';

type Mode = 'system' | 'light' | 'dark';
const MODES: Mode[] = ['system', 'light', 'dark'];

const THEME_CSS = `
  :root {
    --sp-bg: #050506;
    --sp-fg: #f4f4f5;
    --sp-muted: #a1a1aa;
    --sp-dim: #71717a;
    --sp-line: rgba(255, 255, 255, 0.08);
    --sp-panel: rgba(255, 255, 255, 0.03);
    --sp-accent: #34d399;
    --sp-glow: rgba(16, 185, 129, 0.10);
  }
  @media (prefers-color-scheme: light) {
    :root:not([data-theme="dark"]) {
      --sp-bg: #fafafa;
      --sp-fg: #18181b;
      --sp-muted: #52525b;
      --sp-dim: #71717a;
      --sp-line: rgba(0, 0, 0, 0.09);
      --sp-panel: rgba(0, 0, 0, 0.03);
      --sp-accent: #059669;
      --sp-glow: rgba(16, 185, 129, 0.08);
    }
  }
  [data-theme="dark"] {
    --sp-bg: #050506;
    --sp-fg: #f4f4f5;
    --sp-muted: #a1a1aa;
    --sp-dim: #71717a;
    --sp-line: rgba(255, 255, 255, 0.08);
    --sp-panel: rgba(255, 255, 255, 0.03);
    --sp-accent: #34d399;
    --sp-glow: rgba(16, 185, 129, 0.10);
  }
  [data-theme="light"] {
    --sp-bg: #fafafa;
    --sp-fg: #18181b;
    --sp-muted: #52525b;
    --sp-dim: #71717a;
    --sp-line: rgba(0, 0, 0, 0.09);
    --sp-panel: rgba(0, 0, 0, 0.03);
    --sp-accent: #059669;
    --sp-glow: rgba(16, 185, 129, 0.08);
  }
  @keyframes sp-rise {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @media (prefers-reduced-motion: reduce) {
    .sp-rise { animation: none; opacity: 1; transform: none; }
  }
`;

export default function LandingPage() {
  const [mode, setMode] = useState<Mode>('system');

  useEffect(() => {
    const root = document.documentElement;
    if (mode === 'system') {
      delete root.dataset.theme;
    } else {
      root.dataset.theme = mode;
    }
    return () => {
      delete root.dataset.theme;
    };
  }, [mode]);

  return (
    <div className="min-h-screen antialiased" style={{ background: 'var(--sp-bg)', color: 'var(--sp-fg)' }}>
      <style>{THEME_CSS}</style>

      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background:
            'radial-gradient(900px 480px at 50% -8%, var(--sp-glow), transparent 70%)',
        }}
      />

      <div className="relative z-10 flex min-h-screen flex-col">
        <nav className="flex items-center justify-between px-6 py-5 sm:px-10">
          <span className="flex items-center gap-2 text-[15px] font-bold tracking-tight">
            <span aria-hidden>🛸</span>
            SpacePilot
          </span>
          <button
            onClick={() => setMode(MODES[(MODES.indexOf(mode) + 1) % MODES.length])}
            className="rounded-md border px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors hover:opacity-80"
            style={{ borderColor: 'var(--sp-line)', background: 'var(--sp-panel)', color: 'var(--sp-muted)' }}
            aria-label={`Theme: ${mode}. Click to change.`}
          >
            {mode}
          </button>
        </nav>

        <main className="flex flex-1 items-center justify-center px-6 pb-24">
          <div
            className="sp-rise mx-auto max-w-4xl text-center"
            style={{ animation: 'sp-rise 0.45s cubic-bezier(0.22, 1, 0.36, 1) both' }}
          >
            <p
              className="mb-6 font-mono text-[11px] uppercase tracking-[0.22em]"
              style={{ color: 'var(--sp-dim)' }}
            >
              MotionVector · Private Runtime
            </p>

            <h1 className="text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-[42px]">
              SkyPilot pilots your cloud servers.
              <br />
              <span style={{ color: 'var(--sp-accent)' }}>SpacePilot</span> pilots your
              generative cinema.
            </h1>

            <p
              className="mx-auto mt-7 max-w-xl text-base leading-relaxed sm:text-lg"
              style={{ color: 'var(--sp-muted)' }}
            >
              A generative cinema runtime for directors and AI agents — resident-VRAM video
              generation, voice mastering, and FastMCP directing tools. In private development.
            </p>

            <div className="mt-9 flex flex-wrap items-center justify-center gap-2.5">
              {['In private development', 'Runtime docs internal'].map((chip) => (
                <span
                  key={chip}
                  className="rounded-full border px-3.5 py-1.5 font-mono text-xs"
                  style={{ borderColor: 'var(--sp-line)', background: 'var(--sp-panel)', color: 'var(--sp-muted)' }}
                >
                  {chip}
                </span>
              ))}
            </div>
          </div>
        </main>

        <footer
          className="flex flex-wrap items-center justify-between gap-3 border-t px-6 py-5 text-xs sm:px-10"
          style={{ borderColor: 'var(--sp-line)', color: 'var(--sp-dim)' }}
        >
          <span>MotionVector program · spacepilot.dev</span>
          <a
            href="https://motionvector.dev"
            className="transition-colors hover:opacity-80"
            style={{ color: 'var(--sp-muted)' }}
          >
            motionvector.dev ↗
          </a>
        </footer>
      </div>
    </div>
  );
}
