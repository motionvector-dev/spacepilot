<div class="mv-wrapper">
  <div class="mv-header">
    <div class="mv-brand">MotionVector Architecture</div>
    <div class="mv-theme-toggle">
      <button onclick="setTheme('system')" class="mv-btn active" id="btn-system">System</button>
      <button onclick="setTheme('dark')" class="mv-btn" id="btn-dark">Dark</button>
      <button onclick="setTheme('light')" class="mv-btn" id="btn-light">Light</button>
    </div>
  </div>

  <div class="mv-content">
    <h1 class="mv-title">The 11/10 Architecture Upgrade</h1>
    <p class="mv-lead">
      Moving the Katana GPU pipeline from a resilient survivor to a hyperscale, world-class video processing engine.
    </p>

    <div class="mv-section">
      <div class="mv-badge">Phase 1</div>
      <h2>Event-Driven State (Replacing MongoDB Polling)</h2>
      <p>
        Currently, the Node backend, DO Orchestrator, and local workers rely on high-frequency polling against MongoDB (using <code>find_one_and_update</code> and heartbeat timestamps) to pass the job baton. This creates race conditions, deadlocks, and fragile "staleness watchdogs."
      </p>
      <p>
        <strong>The Upgrade:</strong> Introduce a true message broker (e.g., AWS SQS or Redis Streams). The backend drops a job onto an <code>upscale-jobs</code> queue. Workers pull from the queue, locking the message via a visibility timeout. If a worker crashes, the timeout expires, and the message is instantly re-queued with exactly-once delivery guarantees.
      </p>
      
      <div class="mv-diagram-container">
        <svg viewBox="0 0 800 300" class="mv-svg" xmlns="http://www.w3.org/2000/svg">
          <!-- Definitions -->
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" class="mv-svg-fill-muted" />
            </marker>
            <marker id="arrow-accent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" class="mv-svg-fill-accent" />
            </marker>
          </defs>

          <!-- Nodes -->
          <rect x="50" y="100" width="140" height="60" rx="6" class="mv-svg-surface" />
          <text x="120" y="135" class="mv-svg-text" text-anchor="middle">Node Backend</text>

          <rect x="300" y="100" width="200" height="60" rx="6" class="mv-svg-accent-surface" />
          <text x="400" y="135" class="mv-svg-text-accent" text-anchor="middle" font-weight="bold">SQS Event Bus</text>

          <rect x="610" y="20" width="140" height="50" rx="6" class="mv-svg-surface" />
          <text x="680" y="50" class="mv-svg-text" text-anchor="middle">Mac Worker</text>

          <rect x="610" y="105" width="140" height="50" rx="6" class="mv-svg-surface" />
          <text x="680" y="135" class="mv-svg-text" text-anchor="middle">RTX 5090</text>

          <rect x="610" y="190" width="140" height="50" rx="6" class="mv-svg-surface" />
          <text x="680" y="220" class="mv-svg-text" text-anchor="middle">Runpod Cluster</text>

          <!-- Lines -->
          <line x1="190" y1="130" x2="290" y2="130" class="mv-svg-stroke-accent" stroke-width="2" marker-end="url(#arrow-accent)" />
          <text x="240" y="120" class="mv-svg-text-muted" font-size="12" text-anchor="middle">Push Job</text>

          <line x1="500" y1="115" x2="600" y2="45" class="mv-svg-stroke-muted" stroke-width="2" marker-end="url(#arrow)" />
          <line x1="500" y1="130" x2="600" y2="130" class="mv-svg-stroke-muted" stroke-width="2" marker-end="url(#arrow)" />
          <line x1="500" y1="145" x2="600" y2="215" class="mv-svg-stroke-muted" stroke-width="2" marker-end="url(#arrow)" />
          
          <text x="560" y="90" class="mv-svg-text-muted" font-size="12" text-anchor="middle">Poll & Lock</text>
        </svg>
      </div>
    </div>

    <div class="mv-section">
      <div class="mv-badge">Phase 2</div>
      <h2>Virtual Fleet Abstraction (Unified Scheduler)</h2>
      <p>
        Currently, the Node backend explicitly codes routing logic for specific hardware (e.g., <code>&lt; 60s -> Mac</code>, <code>&gt; 1800s -> Runpod</code>). Adding new hardware requires rewriting backend logic.
      </p>
      <p>
        <strong>The Upgrade:</strong> Extract dispatch into an independent Scheduler Service. The backend submits a job ("45s, 720p") statelessly. The Scheduler maintains a live inventory of connected nodes via WebSockets, evaluates real-time capacity and cost margins, and routes the job to the optimal tier automatically.
      </p>

      <div class="mv-diagram-container">
        <svg viewBox="0 0 800 350" class="mv-svg" xmlns="http://www.w3.org/2000/svg">
          <!-- Gateway -->
          <rect x="50" y="150" width="120" height="50" rx="6" class="mv-svg-surface" />
          <text x="110" y="180" class="mv-svg-text" text-anchor="middle">API Gateway</text>

          <!-- Scheduler -->
          <rect x="250" y="130" width="180" height="90" rx="6" class="mv-svg-accent-surface" />
          <text x="340" y="165" class="mv-svg-text-accent" text-anchor="middle" font-weight="bold">Fleet Scheduler</text>
          <text x="340" y="195" class="mv-svg-text-accent" text-anchor="middle" font-size="12">Live Node Inventory</text>

          <!-- Hardware Tiers -->
          <rect x="550" y="40" width="200" height="50" rx="6" class="mv-svg-surface" />
          <text x="650" y="70" class="mv-svg-text" text-anchor="middle">Tier 0: Local Macs ($0)</text>

          <rect x="550" y="110" width="200" height="50" rx="6" class="mv-svg-surface" />
          <text x="650" y="140" class="mv-svg-text" text-anchor="middle">Tier 1: Local 5090 ($0)</text>

          <rect x="550" y="180" width="200" height="50" rx="6" class="mv-svg-surface" />
          <text x="650" y="210" class="mv-svg-text" text-anchor="middle">Tier 2: Runpod Spot ($)</text>

          <rect x="550" y="250" width="200" height="50" rx="6" class="mv-svg-surface" />
          <text x="650" y="280" class="mv-svg-text" text-anchor="middle">Tier 3: Modal Serverless ($$)</text>

          <!-- Connections -->
          <line x1="170" y1="175" x2="240" y2="175" class="mv-svg-stroke-muted" stroke-width="2" marker-end="url(#arrow)" />
          
          <path d="M 430 150 C 480 150, 500 65, 540 65" fill="none" class="mv-svg-stroke-accent" stroke-width="2" marker-end="url(#arrow-accent)" stroke-dasharray="4" />
          <path d="M 430 165 C 480 165, 500 135, 540 135" fill="none" class="mv-svg-stroke-accent" stroke-width="2" marker-end="url(#arrow-accent)" stroke-dasharray="4" />
          <path d="M 430 185 C 480 185, 500 205, 540 205" fill="none" class="mv-svg-stroke-accent" stroke-width="2" marker-end="url(#arrow-accent)" stroke-dasharray="4" />
          <path d="M 430 200 C 480 200, 500 275, 540 275" fill="none" class="mv-svg-stroke-accent" stroke-width="2" marker-end="url(#arrow-accent)" stroke-dasharray="4" />
        </svg>
      </div>
    </div>

    <div class="mv-grid">
      <div class="mv-card">
        <h3>Unified Inference Runtime (ONNX)</h3>
        <p>
          Maintaining separate execution paths (CoreML vs PyTorch/TensorRT) invites visual drift and duplicated maintenance. Compiling models to <strong>ONNX</strong> or <strong>Apache TVM</strong> guarantees mathematical equivalence. The exact same graph executes natively via CoreML Execution Provider on Macs, and TensorRT on NVIDIA, enforcing true bit-exact parity across the fleet.
        </p>
      </div>
      <div class="mv-card">
        <h3>Distributed Tracing (OpenTelemetry)</h3>
        <p>
          Flattening pod errors into a Mongo string field is a stopgap. Wrapping every pipeline stage in an <strong>OTel Span</strong> provides a unified waterfall trace. When a job fails, centralized dashboards (Datadog/Honeycomb) reveal exactly which pod, host, and <code>ffmpeg</code> subprocess failed, alongside VRAM metrics, eliminating SSH-driven debugging.
        </p>
      </div>
    </div>
  </div>
</div>

<style>
/* MotionVector Brand Core */
:root {
  /* Default to dark mode per MV guidelines */
  --mv-bg: #000000;
  --mv-surface: #050506;
  --mv-border: #27272a;
  --mv-text: #fafafa;
  --mv-text-muted: #a1a1aa;
  --mv-accent: #60a5fa;
  --mv-accent-dim: rgba(96, 165, 250, 0.1);
  --mv-accent-border: rgba(96, 165, 250, 0.3);
}

:root[data-theme="light"] {
  --mv-bg: #ffffff;
  --mv-surface: #f4f4f5;
  --mv-border: #e4e4e7;
  --mv-text: #09090b;
  --mv-text-muted: #71717a;
  --mv-accent: #3b82f6;
  --mv-accent-dim: rgba(59, 130, 246, 0.1);
  --mv-accent-border: rgba(59, 130, 246, 0.3);
}

/* Base Wrapper */
.mv-wrapper {
  background-color: var(--mv-bg);
  color: var(--mv-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.6;
  padding: 0;
  margin: 0;
  min-height: 100vh;
  transition: background-color 0.1s ease, color 0.1s ease;
  /* Motion grammar: exits fast, in place */
}

/* Header & Toggles */
.mv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid var(--mv-border);
  background-color: var(--mv-surface);
}

.mv-brand {
  font-weight: 600;
  font-size: 1.1rem;
  letter-spacing: -0.02em;
}

.mv-theme-toggle {
  display: flex;
  gap: 0.5rem;
  background-color: var(--mv-bg);
  padding: 0.25rem;
  border-radius: 6px;
  border: 1px solid var(--mv-border);
}

.mv-btn {
  background: transparent;
  border: none;
  color: var(--mv-text-muted);
  padding: 0.25rem 0.75rem;
  font-size: 0.85rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.mv-btn:hover {
  color: var(--mv-text);
}

.mv-btn.active {
  background-color: var(--mv-surface);
  color: var(--mv-text);
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

/* Typography */
.mv-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 3rem 2rem;
}

.mv-title {
  font-size: 2.5rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-top: 0;
  margin-bottom: 1rem;
}

.mv-lead {
  font-size: 1.25rem;
  color: var(--mv-text-muted);
  margin-bottom: 4rem;
  max-width: 80%;
}

.mv-badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--mv-accent);
  margin-bottom: 0.5rem;
}

.mv-section h2 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-top: 0;
  margin-bottom: 1rem;
  letter-spacing: -0.01em;
}

.mv-section {
  margin-bottom: 5rem;
}

.mv-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
}

.mv-card {
  background-color: var(--mv-surface);
  border: 1px solid var(--mv-border);
  border-radius: 8px;
  padding: 1.5rem;
}

.mv-card h3 {
  margin-top: 0;
  font-size: 1.1rem;
}

.mv-card p {
  color: var(--mv-text-muted);
  font-size: 0.95rem;
  margin-bottom: 0;
}

/* SVG Styling synced with CSS Variables */
.mv-diagram-container {
  background-color: var(--mv-surface);
  border: 1px solid var(--mv-border);
  border-radius: 12px;
  padding: 2rem;
  margin-top: 2rem;
  display: flex;
  justify-content: center;
}

.mv-svg {
  width: 100%;
  max-width: 800px;
  height: auto;
}

.mv-svg-surface {
  fill: var(--mv-bg);
  stroke: var(--mv-border);
  stroke-width: 2;
}

.mv-svg-accent-surface {
  fill: var(--mv-accent-dim);
  stroke: var(--mv-accent-border);
  stroke-width: 2;
}

.mv-svg-text {
  fill: var(--mv-text);
  font-family: inherit;
  font-size: 14px;
}

.mv-svg-text-accent {
  fill: var(--mv-accent);
  font-family: inherit;
  font-size: 14px;
}

.mv-svg-text-muted {
  fill: var(--mv-text-muted);
  font-family: inherit;
  font-size: 14px;
}

.mv-svg-stroke-muted {
  stroke: var(--mv-border);
}

.mv-svg-stroke-accent {
  stroke: var(--mv-accent);
}

.mv-svg-fill-muted {
  fill: var(--mv-border);
}

.mv-svg-fill-accent {
  fill: var(--mv-accent);
}
</style>

<script>
// Check local preference or system preference for initial load
const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
let currentMode = 'system';

function updateActiveButton(mode) {
  document.getElementById('btn-system').classList.remove('active');
  document.getElementById('btn-dark').classList.remove('active');
  document.getElementById('btn-light').classList.remove('active');
  document.getElementById('btn-' + mode).classList.add('active');
}

function setTheme(mode) {
  currentMode = mode;
  if (mode === 'system') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', mode);
  }
  updateActiveButton(mode);
}

// Initialize button state
updateActiveButton('system');
</script>
