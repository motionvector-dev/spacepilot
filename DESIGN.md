---
name: pluto-studio-design-system
version: 2.5.0
author: Antigravity Team
description: |
  Comprehensive design system specification for Pluto Studio + MotionVector.
  Inspired by Cardboard (usecardboard.com), Diffusion Studio, DaVinci Resolve 19,
  Adobe Premiere Pro, Descript, and Linear/Claude Design Systems.

tokens:
  color:
    background:
      root: "#07080c"
      panel: "#0d0f15"
      card: "#141720"
      raised: "#1a1e2a"
      glass: "rgba(13, 15, 21, 0.78)"
      glass_card: "rgba(20, 23, 32, 0.85)"
    border:
      subtle: "rgba(255, 255, 255, 0.07)"
      medium: "rgba(255, 255, 255, 0.12)"
      highlight: "rgba(255, 255, 255, 0.22)"
      focus: "rgba(56, 189, 248, 0.55)"
    accent:
      cyan: "#38bdf8"
      blue: "#3b82f6"
      indigo: "#6366f1"
      purple: "#a855f7"
      emerald: "#10b981"
      amber: "#f59e0b"
      rose: "#f43f5e"
    text:
      primary: "#f8fafc"
      secondary: "#cbd5e1"
      muted: "#94a3b8"
      dim: "#64748b"
      inverse: "#07080c"
    track:
      video: "#3b82f6"
      vector: "#8b5cf6"
      audio_voice: "#10b981"
      audio_bgm: "#f59e0b"
      playhead: "#ef4444"
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

# Pluto Studio Design System (DESIGN.md)

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
