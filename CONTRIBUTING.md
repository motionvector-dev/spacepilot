# Contributing to SpacePilot

Thanks for considering a contribution. The bar is low on ceremony and high on
truth.

## What this project is

SpacePilot is a local-first inference orchestrator for single-owner AI
compute fleets. It runs AI models on machines you already own, tells you
honestly what fits before you download it, and records what actually
happened after. It has an OpenAI-compatible `/v1` surface, a FastMCP tool
server for coding agents, a zero-build local web cockpit, and a measured
model registry.

Two rules govern everything here, from `AGENTS.md`:

- **Execution over ceremony.** Skip bureaucratic process; bias toward
  working code with real receipts (measurements, test output, benchmark
  rows).
- **Strict tests before implementation** on production paths. Reproduce
  red → fix green → refactor. Exploratory spikes are exempt until they land
  in production paths.

## Project standards

- **Python 3.11+**, declared in `pyproject.toml` (`requires-python`).
- **Install**: `uv tool install spacepilot` (preferred) or
  `pip install spacepilot`.
- **Test locally before a PR:**

  ```bash
  python -m pytest tests/ -q
  ```

  CI runs the same suite on GitHub-hosted runners. Do not trust a hardcoded
  test count anywhere in the tree — check CI for the current number.

- **Commit shape**: imperative subject, short body that says *why* not
  *what*, refs the PR/issue. No AI-generated filler. `git add` by path, never
  `git add -A` — some paths in this repo are build artifacts (`.venv/`,
  `build/`, `spacepilot.egg-info/`, `landing/node_modules/`).

## What a good PR looks like

- **Scope**: one thing. A PR that changes a driver and a registry row is
  fine; a PR that changes the driver and the `/v1` surface and a route table
  and adds a feature is three PRs.
- **Tests**: if it changes behavior, it changes tests. A test that passes
  against the broken code is not a test — when fixing a bug, prove the new
  test *fails* on the original behavior before believing it.
- **Honesty**: every claim in the README, CHANGELOG, docstring, or
  `docs/design/*.md` must be true at the time it is written. If a claim
  about "works" or "measured" does not survive review, fix the claim, not
  the test.

## Note: `AGENTS.md` is the real rulebook

`AGENTS.md` at repo root is the instructions this project hands to coding
agents (Claude Code, Codex, Cursor, Copilot, etc.). Everyone works from the
same document — contributors included. Read it before your first PR; it
explains context that is easy to break silently (the pip-less interpreter
rule, the packaging sanity test, the `runtimes` gate, the registry hook that
regenerates `spacepilot/web/registry.json` and the landing snapshot when
model/yaml data moves).

Run `tools/install_hooks.sh` once after clone to set up `core.hooksPath`.

## The CI gate and its expectations

CI runs on every PR and on pushes to `main` / `dev` / `main-*` branches:

- **pytest** — the full suite
- **packaging** — builds the wheel into a clean venv and runs CLI smoke
  tests (defends against undeclared imports and stale build artifacts)
- **security** — `pip-audit` for known CVEs + `bandit` against
  `.bandit-baseline.json` (23 known pre-existing findings, recorded; the
  gate fails on *new* findings)

Do not open a PR that skips tests. If your change needs a baseline bump,
say so explicitly in the PR body with the regeneration command and the new
count.

## Relationship between this repo and its siblings

| repo | relationship |
|---|---|
| `motionvector-dev/spacepilot` (this one) | the core — CLI, `/v1`, MCP, web cockpit, registry |
| `motionvector-dev/spacebar` | the macOS menu bar app, **read-only** vs SpacePilot — separate cadence, never vendored |
| spacepilot.dev | the landing page, deploys from `landing/` in this repo |

## Licensing

Apache-2.0, same license as every registry model card SpacePilot cites.
Contributions on PRs are interpreted identically (Apache-2.0 from the fork
moment onward).
