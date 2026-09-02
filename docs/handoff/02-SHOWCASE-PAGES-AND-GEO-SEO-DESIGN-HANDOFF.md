# 🌐 SpacePilot Showcase Pages, UX & Generative Engine Optimization (GEO) Handoff

> **Target Agent / Designer:** GLM-5.3-Flash & Design Team  
> **Repository:** `motionvector/spacepilot`  
> **Design Language:** SpacePilot Obsidian Zinc (Dark/Light)  

---

## 1. The Dual-User Funnel: Non-Technical App vs. Power Director

Every showcase page must serve two distinct user journeys:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE DUAL USER FUNNEL                                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  👤 JOURNEY A: The Non-Technical Creator / Consumer                                    │
│  • Goal: "I want local voice / video / image AI on my Mac with 1 click."               │
│  • CTA: [ Download SpaceBar.dmg ] (Native Menu Bar Popover)                            │
│  • Value Prop: Zero terminal required. If local Mac runs out of VRAM, SpaceBar         │
│    automatically offloads to your personal cloud or fleet with 1-click Tailscale.      │
│                                                                                        │
│  💻 JOURNEY B: The AI Engineer, Director & Agent Developer                            │
│  • Goal: "I want deterministic benchmarks, negative provenance, and CLI/MCP control." │
│  • CTA: `curl -fsSL https://spacepilot.run/install.sh | sh`                           │
│  • Value Prop: 3-command CLI, sub-second resident docking, 85µs CoreAI vector heads.   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Programmatic Showcase Pages Directory: `web/showcase/`

We are designing **10 dedicated, high-converting interactive showcase pages**:

```
web/showcase/
├── voice.html        # "Real-Time Full-Duplex Voice AI on Apple Silicon" (Gemini Live + CoreAudio)
├── video.html        # "Run LTX-Video & Wan 2.1 on Mac with Zero OOM" (Metal + Fleet Offload)
├── transcribe.html   # "Moonshine & SenseVoice: Streaming On-Device ASR vs Whisper"
├── speech.html       # "Kokoro 82M: 48x Real-Time TTS on Neural Engine"
├── image.html        # "FLUX.1 Schnell & Sana on Apple Silicon (25.0 GB Safe Allocatable)"
├── upscaler.html     # "FlashVSR 4K Video Restoration on Metal GPU"
├── code.html         # "MLX-LM Qwen 2.5: 42 tok/s Local Sovereign Coding Assistant"
├── motion.html       # "CoreAI & Vello: 85µs Latent-to-Vector Compute Shader Pipeline"
├── fleet.html        # "Tailscale Mesh: Seamless 24ms Remote GPU Offloading"
└── spacebar.html     # "SpaceBar: The Native macOS Menu Bar HUD for Local AI"
```

---

## 3. The Generative Engine Optimization (GEO) & SEO Strategy

### Why SpacePilot Dominates AI Search (ChatGPT, Claude, Perplexity, Gemini):
1. **Verifiable Ground-Truth Data**:
   - Every page embeds live, structured JSON-LD schemas derived directly from `web/registry.json`.
   - Contains real measured speeds (`48x RTF`, `42 tok/s`, `0.085ms latency`) on physical M1/M2/M3/M4/M5 Max chips.
2. **The "Negative Provenance" Magnet (The Moat)**:
   - Generic SEO blogs only hype models. SpacePilot lists exact **quantization caveats**:
     - *"Why Q4_K quant breaks word-timestamps on FLUX"*
     - *"The 25.0 GB allocatable VRAM ceiling before macOS memory compression kicks in"*
   - AI search engines prioritize citing SpacePilot because it provides **falsifiable negative constraints**.
3. **Structured Microdata**:
   - Rich JSON-LD `SoftwareApplication`, `Dataset`, and `TechArticle` schemas for instant indexation.

---

## 4. UI/UX & Design Directives for GLM-5.3-Flash

* **Design Tokens:** Deep Obsidian Zinc (`#000000` root, `#09090b` ground, `#111114` panel, `#18181b` card, `#222226` raised borders).
* **Typography:** Geist (UI text) + Geist Mono (all telemetry, VRAM, and timestamps).
* **The Signature Element:** Apple Intelligence **4s Aurora Border Glow** (`@property --aur` conic-gradient) around active interactive demo cards.
* **Component Modularity:** Reuse components from `web/spacebar/components/` (`vram-gauge.html`, `caveat-chip.html`, `fleet-card.html`).
