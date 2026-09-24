# SpacePilot v2.9.0 Release Notes

**Local-first inference you can verify, not just believe.**

SpacePilot runs generative AI on hardware you already own — Mac, engine box, GPU rig — and measures what it can actually do on each one, so readiness is empirical rather than claimed.

---

### What's New in v2.9.0

#### 1. CLI honesty, end to end

- **Thinking is explicit.** `--thinking on` is the opt-in; the default stays off. A transcript that never closes its think block is a failed measurement, not a speed number.
- **Route readiness is real.** A cached route reports ready only when the installed runtime can actually load the architecture — no more "green" rows for models that would fail at load time.
- **The download bar counts what exists.** Bytes already on disk count, including an in-flight partial shard, so progress reads truthfully also on a resumed download.
- **One truth per surface.** Local status, memory displays, and checkpoint listings now agree with each other — what the CLI says and what the cockpit shows come from the same numbers, not two different readings of the world.

#### 2. Runtime installs that don't wreck each other

- Runtimes install into **their own uv-managed venvs** — mlx-lm gets its own, so installing or upgrading it never degrades the core interpreter (the concretely painful case: mlx-lm pins pin opencv down from 5.x to 4.x in a shared env).
- The **installer describes without performing**: asking what an install would do no longer side-effects your machine.
- A **failed isolated install never removes a working route**. A broken attempt at a better tool cannot take away the one that already worked.

#### 3. Packaging, for real this time

- `web/` ships inside the wheel — no more re-downloading static assets post-install, no resolution into a Python install tree.
- Version is read from the package itself, not duplicated and drifted across files.
- The whole web tree is gated, the static mount is covered by its test, `state_root` is hoisted properly.

#### 4. MCP and HTTP agree

- The MCP server and the HTTP API now **match**: same routes, same semantics, and — when something goes wrong — the same honest error text instead of an MCP-shaped shrug.

#### 5. Core AI groundwork (not served yet, and honest about that)

- The **Core AI tokenizer** ships here: renders a Qwen chat prompt to raw token ids with a **pinned sentinel revision**, lazy transformers import (imports cleanly without transformers installed). CI green.
- The **Qwen3.5-9B Core AI port** is specced and gated (`docs/design/coreai-qwen35-9b-port.md` for the detail). The int8 bundle exists, G1/G3 gates pass, and the train-arithmetic gate item fails — checked, and it fails the **base model**, not the bundle. The bundle answers it correctly when thinking is on. **It is not served in this release**; the spec keeps int8 as the ship until a long gate passes on it.
- **Five new registered models:** MiMo-V2.6 distill, Gemma 4 26B-A4B, Maple, Bonsai 2 27B, LFM2.5-8B-A1B.

#### 6. Registry

- **Qwen1.5-MoE-A2B-7B-chat-4bit** measured on M1 Max 32GB: 44.27 tok/s, revision-pinned (`cf11600`), 8.78 GB peak, recovered in this release cycle from an uncommitted worktree before it was lost.

---

### Also in this release

- Merge trains (`main-<date>`) are now CI-gated for PRs.
- Reference docs (AgentWorth contract, build plan, remote pipeline sketch) refreshed in-tree.
- CHANGELOG.md now exists (Keep a Changelog format) — this file ends its solo run as the only release record.

### Install

```bash
uv tool install spacepilot
```

Or as a library: `pip install spacepilot`. Full docs at [spacepilot.dev](https://spacepilot.dev) or via `spacepilot --help` locally.
