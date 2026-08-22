import { useEffect, useState } from 'react';

type Mode = 'system' | 'light' | 'dark';
type FormState = 'idle' | 'pending' | 'success' | 'error';
const MODES: Mode[] = ['system', 'light', 'dark'];

const THEME_CSS = `
  :root {
    --sp-bg: #050506;
    --sp-fg: #f4f4f5;
    --sp-muted: #a1a1aa;
    --sp-dim: #71717a;
    --sp-line: rgba(255, 255, 255, 0.08);
    --sp-line-strong: rgba(255, 255, 255, 0.16);
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
      --sp-line-strong: rgba(0, 0, 0, 0.18);
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
    --sp-line-strong: rgba(255, 255, 255, 0.16);
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
    --sp-line-strong: rgba(0, 0, 0, 0.18);
    --sp-panel: rgba(0, 0, 0, 0.03);
    --sp-accent: #059669;
    --sp-glow: rgba(16, 185, 129, 0.08);
  }
  @keyframes sp-rise {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @media (prefers-reduced-motion: reduce) {
    .sp-rise { animation: none !important; opacity: 1; transform: none; }
  }
`;

export default function LandingPage() {
  const [mode, setMode] = useState<Mode>('system');
  const [email, setEmail] = useState('');
  const [formState, setFormState] = useState<FormState>('idle');
  const [feedback, setFeedback] = useState('');

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

  const joinWaitlist = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || !trimmed.includes('@') || !trimmed.includes('.')) {
      setFormState('error');
      setFeedback('Please enter a valid email address.');
      return;
    }
    setFormState('pending');
    setFeedback('');
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 10000);
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmed, source: 'spacepilot.dev' }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Something went wrong.');
      setFormState('success');
      setFeedback(data.message || "You're on the list! We'll reach out when early access opens.");
    } catch (err) {
      setFormState('error');
      setFeedback(err instanceof Error && err.message ? err.message : 'Failed to join the waitlist. Try again.');
    }
  };

  return (
    <div className="min-h-screen antialiased" style={{ background: 'var(--sp-bg)', color: 'var(--sp-fg)' }}>
      <style>{THEME_CSS}</style>

      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background: 'radial-gradient(900px 480px at 50% -8%, var(--sp-glow), transparent 70%)',
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
              MotionVector · Generative Cinema Runtime
            </p>

            <h1 className="text-4xl font-extrabold leading-[1.12] tracking-tight sm:text-[42px]">
              Every frame begins as intent.
              <br />
              <span style={{ color: 'var(--sp-accent)' }}>SpacePilot</span> compiles intent into
              cinema.
            </h1>

            <p
              className="mx-auto mt-7 max-w-xl text-base leading-relaxed sm:text-lg"
              style={{ color: 'var(--sp-muted)' }}
            >
              A generative cinema runtime for directors and AI agents — open-weight video and
              audio models run directly on GPUs you control, local or cloud, directed through
              code, UI, or MCP tools.
            </p>

            {formState === 'success' ? (
              <p
                className="mx-auto mt-10 max-w-md rounded-lg border px-5 py-4 text-sm font-medium"
                role="status"
                style={{ borderColor: 'var(--sp-accent)', color: 'var(--sp-accent)', background: 'var(--sp-panel)' }}
              >
                {feedback}
              </p>
            ) : (
              <form
                onSubmit={joinWaitlist}
                className="mx-auto mt-10 flex max-w-md items-stretch gap-2 rounded-xl border p-1.5 transition-shadow focus-within:shadow-[0_0_0_3px_var(--sp-glow)]"
                style={{ borderColor: formState === 'error' ? '#f43f5e' : 'var(--sp-line-strong)', background: 'var(--sp-panel)' }}
              >
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (formState === 'error') {
                      setFormState('idle');
                      setFeedback('');
                    }
                  }}
                  placeholder="Work email address"
                  aria-label="Work email address"
                  className="min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-[color:var(--sp-dim)]"
                  style={{ color: 'var(--sp-fg)' }}
                />
                <button
                  type="submit"
                  disabled={formState === 'pending'}
                  className="shrink-0 rounded-lg px-4 py-2.5 text-sm font-bold transition-all hover:opacity-90 disabled:opacity-50"
                  style={{ background: 'var(--sp-accent)', color: '#04120c' }}
                >
                  {formState === 'pending' ? 'Joining…' : 'Request Early Access'}
                </button>
              </form>
            )}

            {formState === 'error' && feedback && (
              <p className="mt-3 text-sm" role="alert" style={{ color: '#f43f5e' }}>
                {feedback}
              </p>
            )}
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
