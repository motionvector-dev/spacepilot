---
name: spacepilot-design-system
version: 2.5.0   # unverified — no dated record of when this was set; do not bump without evidence
author: Antigravity Team
description: |
  Comprehensive design system specification for SpacePilot + MotionVector.
  Inspired by Cardboard (usecardboard.com), Diffusion Studio, DaVinci Resolve 19,
  Adobe Premiere Pro, Descript, and Linear/Claude Design Systems.

tokens:
  color:
    background:
      root: "#000000"
      ground: "#09090b"
      panel: "#111114"
      card: "#18181b"
      raised: "#222226"
      glass: "rgba(17, 17, 20, 0.85)"
      glass_card: "rgba(24, 24, 27, 0.9)"
    border:
      subtle: "rgba(255, 255, 255, 0.08)"
      medium: "rgba(255, 255, 255, 0.14)"
      highlight: "rgba(255, 255, 255, 0.22)"
      focus: "rgba(255, 255, 255, 0.35)"
    semantic:
      emerald: "#10b981"
      amber: "#f59e0b"
      rose: "#f43f5e"
    text:
      primary: "#fafafa"
      secondary: "#a1a1aa"
      muted: "#71717a"
      dim: "#52525b"
      inverse: "#09090b"
    track:
      v2: "#fafafa"
      v1: "#a1a1aa"
      audio: "#10b981"
      playhead: "#f43f5e"
  typography:
    font_sans: "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    font_mono: "'JetBrains Mono', 'SF Mono', Consolas, monospace"
    font_display: "'Plus Jakarta Sans', system-ui, sans-serif"
  elevation:
    shadow_sm: "0 1px 2px rgba(0,0,0,0.4)"
    shadow_md: "0 4px 12px rgba(0,0,0,0.5)"
    shadow_lg: "0 12px 32px rgba(0,0,0,0.65)"
    shadow_glow_cyan: "0 0 24px rgba(56, 189, 248, 0.25)"
    shadow_glow_emerald: "0 0 24px rgba(16, 185, 129, 0.25)"
  spacing:
    space_0: "0"
    space_1: "4px"
    space_2: "8px"
    space_3: "12px"
    space_4: "16px"
    space_5: "20px"
    space_6: "24px"
    space_7: "32px"
    space_8: "40px"
    space_9: "48px"
    space_10: "64px"
    space_11: "80px"
    space_12: "96px"
  component_height:
    height_xs: "24px"
    height_sm: "28px"
    height_md: "32px"
    height_lg: "36px"
    height_xl: "40px"
    height_2xl: "48px"
    header_bar: "52px"
    timeline_toolbar: "28px"
    timeline_track: "36px"
    timeline_ruler: "20px"
    timeline_footer: "160px"
  breakpoints:
    mobile: "< 768px"
    tablet: "768px – 1024px"
    desktop: ">= 1024px"
---

# SpacePilot Design System (DESIGN.md)

**Status**: Current
**Verified**: 2026-08-22 (`version: 2.5.0` above is unverified — no dated record of when it was set)
**Supersedes / Superseded by**: none

This spec covers the UI layer only. The backend it talks to is the modular
`spacepilot/api/routes/` FastAPI app, live on main with 14 route modules
(assets, audio, billing, checkpoints, compute, engines, generate, gpu, health,
lora, recipes, storyboard, views, `__init__`).

## 1. Visual Hierarchy & Philosophy
- **Obsidian Dark Precision**: Deep dark UI backgrounds prevent color perception bias when color-grading video and viewing high-contrast LaTeX vector animations.
- **Glassmorphism & Depth**: Translucent surfaces () provide depth while keeping user focus on the central video canvas.
- **Micro-Precision Monospace**: SMPTE timecodes (), LTX generation latencies, and LaTeX math equations use fixed-pitch JetBrains Mono with tabular numbers.
- **Magnetic Timeline Interaction**: Tracks feature clear visual hierarchies: Video Plate (blue), MotionVector (purple), Kokoro Audio (emerald), Ambient Music (amber).

## 2. Key Components
1. **Header HUD**: Spot GPU instance health, VRAM gauge, real-time accrued cost meter, and mode switcher tabs.
2. **AI Director Storyboard**: 5-scene documentary reel with live KaTeX formula rendering, Take A/B/C auditions, and 1-click batch rendering.
3. **Vibe Canvas Viewport**: 16:9 responsive video container with live draggable glass overlay card and A/B split-screen comparison slider.
4. **MotionVector Inspector**: Dedicated LaTeX formula editor, color swatches, position presets, and P0 4K composite trigger.
5. **Multi-Track Timeline**: DaVinci-grade time ruler with tick marks, playhead with red diamond marker, zoom controls, solo/mute buttons, and audio waveform visualization.
6. **Command Palette ()**: Fast search and trigger for all studio workflows.

## 3. Spacing & Sizing Scale

## 4. Responsive & Container Queries
