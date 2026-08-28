# 🛸 SpacePilot & SpaceBar — Master Handoff Suite

This directory contains the canonical handoff blueprints and specifications for **GLM-5.3-Flash** and the engineering team across UI design, showcase pages, and systems architecture:

---

### 📂 Handoff Documents Overview:

1. **[`01-MODALITIES-IMPLEMENTATION-REGISTRY-HANDOFF.md`](./01-MODALITIES-IMPLEMENTATION-REGISTRY-HANDOFF.md)**
   * **Scope:** Backend drivers, model recipes (`.yaml`), 10 modality execution contracts, and Apple Silicon 25.0 GB UMA working-set bounds.
   * **Key Modalities:** `run voice`, `run transcribe`, `run speech`, `run music`, `run image`, `run video`, `run upscaler`, `run code`, `run vlm`, `run motion`.

2. **[`02-SHOWCASE-PAGES-AND-GEO-SEO-DESIGN-HANDOFF.md`](./02-SHOWCASE-PAGES-AND-GEO-SEO-DESIGN-HANDOFF.md)**
   * **Scope:** The 10 public interactive showcase pages (`web/showcase/`), Generative Engine Optimization (GEO) strategy, and the dual-user funnel (Mac App for consumers vs CLI/MCP for AI agents).

3. **[`03-SPACEBAR-MASTER-DESIGN-SPEC-AND-REVIEW.md`](./03-SPACEBAR-MASTER-DESIGN-SPEC-AND-REVIEW.md)**
   * **Scope:** The complete 19.2 KB Principal Design Review authored by GLM-5.3-Flash covering:
     - The rebased 25.0 GB UMA working-set odometer and hatched caution zone.
     - Apple Intelligence 4s `@property --aur` conic-gradient Aurora border shader.
     - Negative provenance caveat chips (`caveat_lookup`) and 1-click CLI copy actions.
     - 120Hz liquid motion curves and macOS native ergonomics (`⌘1`–`⌘5`, `Space` pause).

4. **[`../web/spacebar/`](../web/spacebar/)**
   * **Modular Component Library:**
     - `tokens.css` (Obsidian Zinc design system + Aurora shader)
     - `components/vram-gauge.html`
     - `components/caveat-chip.html`
     - `components/fleet-card.html`
     - `components/telemetry-grid.html`
     - `states/` (Active, Remote Fleet, Caveated, Idle)
