# 🛸 SpaceBar: The Definitive "Clicky Killer" Frontend & App Specification

> **Target Frontend Architect / Coder:** Claude 3.7 / 3.5 Opus (or Sonnet)  
> **Repository:** `motionvector/spacepilot`  
> **Status:** Implementation Blueprint  
> **Mission:** Build the world's most beautiful, responsive, and sovereign macOS Menu Bar HUD & Floating Assistant (`SpaceBar`), completely destroying the clunky, expensive $12/hr cloud wrapper model of Clicky.

---

## 1. The Core Product Thesis: Why SpaceBar Destroys Clicky

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CLICKY (THE CLOUD TOLL) vs. SPACEBAR (SOVEREIGN HUD)                      │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│  👾 Farza's Clicky:                                                                                         │
│  • A floating blue toy character on your screen.                                                           │
│  • $0.20/min OpenAI Realtime + Claude Vision API bills ($12/hour continuous drain).                         │
│  • Inaccurate screen vision coordinates: clicks wrong buttons, breaks on UI layout shifts.                  │
│  • Zero knowledge of hardware: cannot mount FLUX, Kokoro, or MLX models.                                    │
│                                                                                                             │
│  🛸 SpaceBar (The Sovereign Clicky Killer):                                                                 │
│  • Native macOS Menu Bar Popover (`360px` Obsidian Zinc glass) + Floating Aurora Island HUD.                │
│  • 100% Free On-Device Execution: Moonshine (ASR) + MLX (LLM) + Kokoro (TTS) at $0.00 forever.              │
│  • 🧠 Physical Machine Load & Thermal Truth (Zero Fan Noise):                                               │
│    - Moonshine Tiny ASR: ~250 MB RAM | ~3% ANE Load (Passive)                                               │
│    - Qwen 2.5 1.5B / Llama-3.2-1B (Intent Router): ~1.10 GB RAM | ~6% GPU Compute at 110+ tok/s             │
│    - Kokoro 82M TTS: ~120 MB RAM | ~4% Metal Compute (48× Real-Time Factor)                                │
│    - TOTAL RESIDENT FOOTPRINT: ~1.47 GB (Leaves >23.5 GB Allocatable Headroom for heavy Studio workflows!)  │
│    - THERMALS: ~39°C to 42°C SOC | 0 RPM Silent Passive Cooling | < 5W Battery Draw (Practically invisible!)│
│  • True Hardware Telemetry: Live 25.0 GB UMA odometer, 42°C SOC, 0 RPM quiet fan, 42 tok/s stream.         │
│  • Typed Deterministic Verbs: Direct DocIR / CLI / WebMCP integration instead of guessing screen pixels.    │
│  • Hybrid Mesh Offload: Seamlessly routes heavy video/3D to remote RTX 5090 clusters over WireGuard (24ms).│
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Visual Design System & Tokens (Obsidian Zinc)

All styling must adhere to [`web/spacebar/tokens.css`](../web/spacebar/tokens.css):

* **Surfaces:**
  - Root: `#000000` | Ground: `#09090b` | Panel: `#111114` | Card: `#18181b` | Raised: `#222226`
  - Border Lines: `rgba(255, 255, 255, 0.08)` to `0.22`
* **Typography:**
  - UI Text: `Geist` / `-apple-system`
  - Telemetry / Numbers / Timestamps: `Geist Mono` / `JetBrains Mono`
* **The Signature Element:**
  - Apple Intelligence **4s Aurora Conic Border Glow** (`@property --aur` conic-gradient cycling Cyber Blue `#3b82f6`, Purple `#8b5cf6`, Emerald `#10b981`, and Cyan `#06b6d4`).
* **120Hz Liquid Motion Curves:**
  - Enter: `200ms cubic-bezier(0.16, 1, 0.3, 1)` (Apple Spring Pop)
  - Dismiss: `140ms cubic-bezier(0.55, 0, 1, 0.45)` (Snappy Exit)
  - Dock: `300ms cubic-bezier(0.16, 1, 0.3, 1)`

---

## 3. The 4 Interactive State Views for Opus to Code

Opus must implement the 4 discrete state surfaces in `web/spacebar/`:

```
┌───────────────────────────────┬─────────────────────────────────────────────────────────────────────────────┐
│ STATE VIEW                    │ VISUAL SPEC & KEY COMPONENTS                                                │
├───────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ 1. `state-idle.html`          │ • Passive ambient state (42°C SOC, 0 RPM fan, 25.0 GB UMA ready).           │
│    (The Sovereign Standby)    │ • "Space..." wake-word listener pulsing subtly at 15% opacity.              │
│                               │ • 1-click Model Mount carousel (FLUX, Kokoro, Qwen, Moonshine).             │
├───────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ 2. `state-active.html`        │ • Active Voice / Inference stream with Apple Intelligence Aurora glow.      │
│    (Full-Duplex Generation)   │ • 120 FPS live audio waveform + 42.4 tok/s streaming throughput counter.    │
│                               │ • Dynamic VRAM fill bar displaying real-time allocation vs 25.0 GB limit.   │
├───────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ 3. `state-remote.html`        │ • Remote Tailscale WireGuard 5090 cluster offload.                          │
│    (Fleet Burst Mode)         │ • Blue left truth-rail + "5090 · 24ms RTT" telemetry badge.                 │
│                               │ • Displays remote queue depth and network throughput.                       │
├───────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ 4. `state-caveated.html`      │ • Negative Provenance banner (`caveat_lookup`).                             │
│    (The Truth Safeguard)      │ • Amber hatched buffer warning if quantization degrades output (e.g. Q4_K). │
│                               │ • 1-click `⌘C` copy action for the equivalent deterministic CLI command.    │
└───────────────────────────────┴─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. macOS Native Ergonomics & Keyboard Contracts

* `⌘1`–`⌘4`: Fast toggle between Modality tabs (Voice, Image, Video, Fleet).
* `Space`: Tap to pause/interrupt speech (sub-1ms buffer flush).
* `⌘C` on any telemetry chip: Copies the exact `spacepilot probe` or `spacepilot run` command to clipboard.
* `Esc`: Closes popover with `140ms` snappy exit curve.

---

## 5. Opus Coding Instructions & File Manifest

When Opus starts coding, it will build and link these files:

```
web/spacebar/
├── index.html              # Master SpaceBar Popover container (360px glass)
├── tokens.css              # Obsidian Zinc design system + Aurora shader
├── components/
│   ├── vram-gauge.html     # Rebased on 25.0 GB UMA limit with hatched warning zone
│   ├── sovereign-orb.html  # 120 FPS radial glass orb + VU audio meter
│   ├── caveat-chip.html    # Negative provenance badge
│   ├── fleet-card.html     # 24ms WireGuard RTT telemetry card
│   └── telemetry-grid.html # 42°C SOC, 0 RPM fan, tok/s stream
└── states/
    ├── state-idle.html
    ├── state-active.html
    ├── state-remote.html
    └── state-caveated.html
```
