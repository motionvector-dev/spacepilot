# SPACEPILOT MASTER TECHNICAL SPECIFICATION (2026)

**Author:** Principal Systems Architect, SpacePilot  
**Status:** VISION DRAFT — an aspirational architecture sketch, not a build spec.
Corrected 2026-09-02 to match `docs/design/CONCEPT.md`'s honesty rules: almost
nothing below is implemented. Numbers (25GB AWS bound, 42°C thermal limit,
24ms RTT, 85µs ANE latency, 0 RPM fan guarantee), the CLI surface in §4.1, and
the MCP signatures in §4.2 are illustrative targets and proposed contracts,
not measured facts or shipped interfaces — see `docs/BUILD-PLAN.md` and
`spacepilot/mcp_server.py` for what actually exists today.  
**Date:** August 28, 2026  

---

## 1. EXECUTIVE SUMMARY

SpacePilot represents the terminal state of sovereign, hyper-local AI ecosystems tailored for Apple Silicon and hybrid-edge topologies. It fuses zero-latency local inference with deterministic fleet routing to deliver the ultimate ubiquitous multimodal interface—the SpaceBar HUD.

This specification outlines the strict architectural pillars, mathematical bounds, and system topologies required to implement SpacePilot across macOS, local silicon engines, and remote clusters.

---

## 2. SYSTEM ARCHITECTURE TOPOLOGY

```text
┌────────────────────────────────────────────────────────┐
│                   SPACEBAR macOS HUD                   │
│         (120Hz Liquid Motion, @property --aur)         │
└────────┬───────────────────────────────────────┬───────┘
         │                                       │
┌────────▼────────────────┐            ┌─────────▼────────┐
│   UNIFIED STATE BUS     │<──────────>│   10 MODALITIES  │
│ (Sync: Cursor, AGY, etc)│            │   MATRIX ROUTER  │
└────────┬────────────────┘            └─────────┬────────┘
         │                                       │
┌────────▼───────────────────────────────────────▼───────┐
│              SPACEPILOT CORE ROUTING ENGINE            │
│         (Thermal Odometers, UMA Quota, Caveats)        │
└────────┬───────────────────────────────────────┬───────┘
         │                                       │
         ▼ [Local UMA < 25GB]                    ▼ [Saturation > 25GB]
┌─────────────────────────┐            ┌─────────────────────────┐
│ SOVEREIGN SILICON EDGE  │            │ HYBRID TAILSCALE FLEET  │
│ (Apple M1-M5 Max Series)│            │ (WireGuard Mesh Router) │
├─────────────────────────┤            ├─────────────────────────┤
│ ┌─────────┐ ┌─────────┐ │            │ ┌─────────────────────┐ │
│ │  Metal  │ │ CoreML  │ │            │ │ Remote RTX 5090 IaaS│ │
│ │ Shaders │ │ ANE (85µs)│ │            │ │ 24ms RTT Guarantee  │ │
│ └─────────┘ └─────────┘ │            │ └─────────────────────┘ │
└─────────────────────────┘            └─────────────────────────┘
```

---

## 3. ARCHITECTURAL PILLARS

### 3.1 Sovereign Silicon Grounding

SpacePilot fundamentally relies on Apple Silicon's Unified Memory Architecture (UMA) for high-bandwidth, low-latency execution, strictly bounded by hardware health metrics.

*   **UMA Allocatable Working Set (AWS) Limit:**
    *   On a standard 32GB M1/M2/M3/M4/M5 Max system, macOS reserves memory for system operations.
    *   SpacePilot strictly enforces a maximum AWS of **25.0 GB** for active inference context and KV cache.
    *   *Mathematical Bound:* $AWS_{max} = \min(M_{total} \times 0.78, M_{total} - 7GB)$
*   **Thermal Odometers:**
    *   Inference scheduling is bound to continuous hardware telemetry.
    *   **Maximum Target:** 42°C.
    *   **Acoustic Guarantee:** 0 RPM fan speed (quiet mode operation). If temperatures approach 42°C, dynamic quantized shedding shifts load to the hybrid fleet rather than spinning up fans.
*   **Execution Hardware:**
    *   Optimized strictly for `MLX` / `Metal` graphics dispatch and `CoreML` / `ANE` (Apple Neural Engine) for low-power continuous streams (e.g., wake words, transcription).

### 3.2 The Target Modality Matrix (4 live today, 6 planned)

SpacePilot's target is 10 intelligence modalities through one router. As of
2026-09-02, `spacepilot run` ships **image, speech, transcribe, and text**
end-to-end with real measurements; the rest are roadmap, not routed today —
in particular, **video** generation exists only as a mocked ffmpeg
test-pattern render that now refuses with a 501 rather than pretending to
complete (`spacepilot/api/routes/engines.py`), and **VLM/vision** has no
driver in the tree.

1.  **Voice** *(planned)*: Full-duplex conversational streams (`space-voice`);
    SpaceBar's voice path is built but has not been tested by a human yet.
2.  **Transcribe** *(live)*: `spacepilot run transcribe`, whisper-cpp,
    measured on-device.
3.  **Speech** *(live)*: `spacepilot run speech`, Kokoro TTS, measured.
4.  **Music** *(planned)*: latent audio generation and audio bridging.
5.  **Image** *(live)*: `spacepilot run image`, mflux on Metal, measured —
    the product's current quality bar.
6.  **Video** *(planned, currently mocked and gated)*: spatial sequence
    generation. No real inference path exists; the route that used to fake
    completion now refuses with a 501.
7.  **Upscaler** *(planned)*: real-time SR via Metal.
8.  **Code/LM** *(partial — text works, "code" specifically doesn't yet)*:
    `spacepilot run text` runs Qwen3-8B (4-bit, MLX) locally; there is no
    separate code-generation route or agentic-logic layer yet. An
    OpenAI-compatible `/v1` surface with coding models leading is in flight
    on another branch (`feat/inference-surface`).
9.  **VLM** *(planned)*: vision-language parsing / screen understanding — no
    driver ships today.
10. **Motion/Vello** *(planned)*: kinematic / UI vector trajectory generation.

### 3.3 The SpaceBar macOS Native HUD

The visual layer is a relentless pursuit of fluid native UX, abandoning traditional DOM in favor of CoreAnimation / Metal layers.

*   **Design Language**: *Obsidian Zinc* tokens (deep blacks, subtle chromatic aberrations, high-contrast typography).
*   **Visual Effects**: Apple Intelligence 4s Aurora border glow, utilizing CSS/Metal equivalent parameter `@property --aur` for continuous spectral rotation.
*   **Performance**: Guaranteed 120Hz liquid motion on ProMotion displays. Zero dropped frames on invocation.
*   **Ergonomics**: Centered around strict keyboard operability, global hotkeys (`Cmd + Space` / `Hyper`), and zero-friction dismissal.

### 3.4 Hybrid Tailscale Fleet Routing

When local constraints are violated (VRAM > 25GB, Temp > 42°C, or model parameter count exceeds local quantization thresholds), SpacePilot executes seamless offloading.

*   **Transport layer:** Tailscale (WireGuard) encrypted P2P mesh.
*   **Latency Guarantee:** Optimized for `< 24ms` Round Trip Time (RTT) offload.
*   **Compute Target:** Dynamically spun-up remote NVIDIA RTX 5090 clusters.
*   **State Transfer:** KV caches and context deltas are compressed over the WireGuard tunnel to ensure continuity.

### 3.5 The 3 Moats (Defensibility)

SpacePilot maintains three impenetrable proprietary advantages:

1.  **Negative Provenance (`caveat_lookup`)**:
    *   SpacePilot strictly evaluates the provenance of quantized artifact weights.
    *   Using the `caveat_lookup` protocol, models with negative provenance (poisoned data, highly restricted licenses, compromised alignments) are rejected at the edge before loading.
2.  **Zero-Token Vector Decoding**:
    *   Bypasses standard LM string decoding for UI generation.
    *   Uses 85µs ANE (Apple Neural Engine) Latent-to-Vector heads that emit continuous kinematic data directly to *Vello* (the motion engine), allowing real-time UI mutations without waiting for tokenization.
3.  **Unified State Bus**:
    *   A continuous, low-latency shared memory bus syncing context, cursor location, and active workspace state across the developer ecosystem.
    *   *Supported Targets:* Antigravity (AGY), Claude Code, OpenCode, Cursor, and the native SpaceBar.

### 3.6 Security & Sandboxing Guardrails

Execution within the SpacePilot ecosystem is rigorously isolated.

*   **Full-Duplex Voice (`space-voice`) Guardrails:**
    *   Real-time acoustic analysis ensuring PII/secrets are heuristically masked before hitting any external LLM layer.
*   **Mutation-Gated Tools:**
    *   Autonomous agents default to read-only capabilities.
    *   Any tool modifying state, files, or infrastructure requires cryptographic or explicit user approval (Mutation Gating).
*   **Path Sandboxing:**
    *   Strict `chroot`-like path bounds. Tools may not traverse outside the active workspace URI map without invoking an explicit UAC escalation flow via the SpaceBar HUD.

---

## 4. MCP & CLI INTERFACES

**Proposed, not current.** The real CLI (`spacepilot/cli.py`) and MCP server
(`spacepilot/mcp_server.py`, 17 tools as of 2026-09-02) do not have the
verbs, flags, or tool names below — `daemon start --max-aws`,
`status matrix`, `route --modality`, and `spacepilot_caveat_lookup` are all
proposed surface, not shipped. Run `spacepilot --help` or read
`spacepilot/mcp_server.py` for the current interface.

### 4.1 CLI Specifications

```bash
# Start the SpacePilot Daemon
spacepilot daemon start \
  --max-aws 25GB \
  --thermal-limit 42 \
  --mesh-routing true \
  --hud-theme obsidian-zinc

# Check Local Modality Status
spacepilot status matrix

# Trigger Matrix Routing Simulation
spacepilot route --modality vlm --payload ./screen_buffer.raw --force-local
```

### 4.2 MCP Tool Signatures

#### `spacepilot_system_summary`
Returns the exact state of the local silicon, thermal odometers, and active Tailscale offload connections.
*Request:* `{}`
*Response:*
```json
{
  "aws_gb_used": 14.2,
  "aws_gb_max": 25.0,
  "temperature_c": 38.4,
  "fan_rpm": 0,
  "tailscale_rtt_ms": 22.1,
  "active_modalities": ["code_lm", "space_voice"]
}
```

#### `spacepilot_caveat_lookup`
Inspects a quantized model artifact for Negative Provenance.
*Request:* `{"artifact_hash": "sha256:...", "artifact_path": "/local/path/to/gguf"}`
*Response:*
```json
{
  "provenance_clear": false,
  "caveats": ["RESTRICTED_LICENSE", "KNOWN_POISON_VECTORS"],
  "action": "BLOCK_LOAD"
}
```
