import { useEffect, useState } from 'react';

type Mode = 'system' | 'light' | 'dark';
type FormState = 'idle' | 'pending' | 'success' | 'error';
const MODES: Mode[] = ['system', 'light', 'dark'];

const STYLES = `
  :root {
    --sp-bg: #050506;
    --sp-fg: #f4f4f5;
    --sp-muted: #a1a1aa;
    --sp-dim: #71717a;
    --sp-line: rgba(255, 255, 255, 0.08);
    --sp-line-strong: rgba(255, 255, 255, 0.16);
    --sp-panel: rgba(255, 255, 255, 0.03);
    --sp-accent: #34d399;
    --sp-accent-ink: #04120c;
    --sp-danger: #f43f5e;
    --sp-glow: rgba(16, 185, 129, 0.10);
    --sp-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --sp-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
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
      --sp-accent-ink: #ffffff;
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
    --sp-accent-ink: #04120c;
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
    --sp-accent-ink: #ffffff;
    --sp-glow: rgba(16, 185, 129, 0.08);
  }

  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body { background: var(--sp-bg); }

  .sp-page {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    position: relative;
    z-index: 10;
    background: var(--sp-bg);
    color: var(--sp-fg);
    font-family: var(--sp-sans);
    -webkit-font-smoothing: antialiased;
  }
  .sp-glow {
    pointer-events: none;
    position: fixed;
    inset: 0;
    z-index: 0;
    background: radial-gradient(900px 480px at 50% -8%, var(--sp-glow), transparent 70%);
  }
  .sp-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px;
  }
  @media (min-width: 640px) { .sp-nav { padding: 20px 40px; } }
  .sp-wordmark {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .sp-theme-btn {
    border-radius: 6px;
    border: 1px solid var(--sp-line);
    background: var(--sp-panel);
    color: var(--sp-muted);
    padding: 4px 10px;
    font-family: var(--sp-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
    transition: opacity 0.15s ease;
  }
  .sp-theme-btn:hover { opacity: 0.8; }
  .sp-main {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 24px 96px;
  }
  .sp-hero {
    margin: 0 auto;
    max-width: 896px;
    text-align: center;
    animation: sp-rise 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
  }
  @media (prefers-reduced-motion: reduce) {
    .sp-hero { animation: none; opacity: 1; transform: none; }
  }
  .sp-eyebrow {
    margin: 0 0 24px;
    font-family: var(--sp-mono);
    font-size: 11px;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--sp-dim);
  }
  .sp-title {
    margin: 0;
    font-size: 36px;
    line-height: 1.12;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
  @media (min-width: 640px) { .sp-title { font-size: 42px; } }
  .sp-accent { color: var(--sp-accent); }
  .sp-sub {
    margin: 28px auto 0;
    max-width: 576px;
    font-size: 16px;
    line-height: 1.6;
    color: var(--sp-muted);
  }
  @media (min-width: 640px) { .sp-sub { font-size: 18px; } }
  .sp-form {
    display: flex;
    align-items: stretch;
    gap: 8px;
    max-width: 448px;
    margin: 40px auto 0;
    padding: 6px;
    border-radius: 12px;
    border: 1px solid var(--sp-line-strong);
    background: var(--sp-panel);
    transition: box-shadow 0.15s ease;
  }
  .sp-form:focus-within { box-shadow: 0 0 0 3px var(--sp-glow); }
  .sp-form.sp-error { border-color: var(--sp-danger); }
  .sp-input {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    outline: none;
    padding: 0 12px;
    font-size: 14px;
    font-family: inherit;
    color: var(--sp-fg);
  }
  .sp-input::placeholder { color: var(--sp-dim); }
  .sp-submit {
    flex-shrink: 0;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 700;
    font-family: inherit;
    background: var(--sp-accent);
    color: var(--sp-accent-ink);
    cursor: pointer;
    transition: opacity 0.15s ease;
  }
  .sp-submit:hover { opacity: 0.9; }
  .sp-submit:disabled { opacity: 0.5; cursor: default; }
  .sp-success {
    max-width: 448px;
    margin: 40px auto 0;
    padding: 16px 20px;
    border-radius: 8px;
    border: 1px solid var(--sp-accent);
    background: var(--sp-panel);
    color: var(--sp-accent);
    font-size: 14px;
    font-weight: 500;
  }
  .sp-alert {
    margin: 12px 0 0;
    font-size: 14px;
    color: var(--sp-danger);
  }
  .sp-footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 20px 24px;
    border-top: 1px solid var(--sp-line);
    font-size: 12px;
    color: var(--sp-dim);
  }
  @media (min-width: 640px) { .sp-footer { padding: 20px 40px; } }
  .sp-footer a {
    color: var(--sp-muted);
    text-decoration: none;
    transition: opacity 0.15s ease;
  }
  .sp-footer a:hover { opacity: 0.8; }
`;

export default function Landing() {
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
    <div className="sp-page">
      <style>{STYLES}</style>

      <div className="sp-glow" aria-hidden />

      <nav className="sp-nav">
        <span className="sp-wordmark">
          <span aria-hidden>🛸</span>
          SpacePilot
        </span>
        <button
          onClick={() => setMode(MODES[(MODES.indexOf(mode) + 1) % MODES.length])}
          className="sp-theme-btn"
          aria-label={`Theme: ${mode}. Click to change.`}
        >
          {mode}
        </button>
      </nav>

      <main className="sp-main">
        <div className="sp-hero">
          <p className="sp-eyebrow">MotionVector · Generative Cinema Runtime</p>

          <h1 className="sp-title">
            Every frame begins as intent.
            <br />
            <span className="sp-accent">SpacePilot</span> compiles intent into cinema.
          </h1>

          <p className="sp-sub">
            A generative cinema runtime for directors and AI agents — open-weight video and
            audio models run directly on GPUs you control, local or cloud, directed through
            code, UI, or MCP tools.
          </p>

          {formState === 'success' ? (
            <p className="sp-success" role="status">
              {feedback}
            </p>
          ) : (
            <form onSubmit={joinWaitlist} className={`sp-form${formState === 'error' ? ' sp-error' : ''}`}>
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
                className="sp-input"
              />
              <button type="submit" disabled={formState === 'pending'} className="sp-submit">
                {formState === 'pending' ? 'Joining…' : 'Request Early Access'}
              </button>
            </form>
          )}

          {formState === 'error' && feedback && (
            <p className="sp-alert" role="alert">
              {feedback}
            </p>
          )}
        </div>
      </main>

      <footer className="sp-footer">
        <span>MotionVector program · spacepilot.dev</span>
        <a href="https://motionvector.dev">motionvector.dev ↗</a>
      </footer>
    </div>
  );
}
