# Working in SpacePilot

Cross-tool agent instructions. `CLAUDE.md` is a symlink to this file, so Claude
Code, Codex, Cursor, Copilot, Antigravity and the rest all read the same rules.
Edit this file, never the symlink.

## What ships, and where it is going

Read `docs/design/VISION.md` first; it holds the grand vision so nobody has to
re-explain it. The short form:

| surface | repo | license and money |
| --- | --- | --- |
| CLI + MCP server | this repo | open source |
| web cockpit, Tauri wrapper later | this repo | open source |
| macbar (SpaceBar menu bar app) | its own repo, to be created | free by default, paid tier later if the value earns $5/month |
| spacepilot.dev | `../spacepilot-landing` | site |

The idea: running AI should be easy, and free when your machine allows it.
When it does not, provisioning a box (RunPod, Modal, an API provider) should be
just as fast and no-nonsense. Start small; the empire is not day one.

Next step for the product: agents take over from the CLI, so a human talks to
SpacePilot in chat while the cockpit shows the data. Not ChatGPT for local AI,
but that plus observability for your fleet, local and remote.

macbar's headline feature is duplex voice, OpenAI-voice style, running locally
when it can: Apple's on-device foundation model (about 3B, free), then
CoreAI/CoreML for open models like Qwen, then a rented box. Free Apple models
come through two doors and MCP fits both: the FoundationModels framework (the
app calls the model, with Tools, so an MCP bridge is a Tool) and App Intents
(Siri and Apple Intelligence understand the request and call macbar, no model
call, no cost). The web cockpit adds WebMCP for browser agents (Chrome origin
trial, not a standard yet). Reference checkouts include
`coreai-*` and `mlx-*`. The `../space-voice` checkout
is a cheap Gemini-Live prototype of the same idea; review it, rebuild from
scratch if it fights the plan. Sources: `docs/design/VISION.md`.

## SpaceBar is read-only, for now (Saurabh, 2026-09-03)

The menu bar app may read from the daemon and ask a model for a reply. It
must not change state: no downloads, installs, checkpoints, launches,
terminates, training, or local writes beyond its own preferences. The
allowlist lives in the app's daemon client; a new route is added there on
purpose, never by accident. Lift this rule in writing when the voice loop has
earned it.

## When Fable drives

Be token efficient. Fable tokens are the rare, expensive ones: Fable plans,
decides, and reviews; everything else goes to the fleet member whose
specialisation fits (Sonnet for edits and browser work, Haiku for scans and
lookups, Opus for adversarial review, agy Flash for vision and grunt work).

A subagent's "not confirmed" survives into the reply as "not confirmed". The
director never rounds it up to a verdict, and never rewrites a doc on the
strength of one. (2026-09-02: an App Intents claim was called wrong on the
basis of a page that never loaded.)

## Interpreter

The repo carries no `.venv`, and bare `python3` is usually the wrong
interpreter — on the primary dev machine it resolves to base conda, which lacks
fastapi. Use the environment where `requirements.txt` was installed, or set
`SPACEPILOT_PYTHON` / `python_bin` in `.spacepilot_config.json` (gitignored, machine-local)
and let the CLI resolve it. Anything that imports `spacepilot/web_api.py` —
including pytest — needs that interpreter.

mflux (`spacepilot/drivers/mflux_driver.py`) is a second, separate interpreter on
purpose: installing mflux into the repo env downgrades opencv-python from 5.0
to 4.14, so it lives in its own conda env and is only ever invoked as a
subprocess, never imported. Point the driver at it with `SPACEPILOT_MFLUX_BIN` or
`"mflux_bin_dir"` in `.spacepilot_config.json` — the bin/ directory of that env
(default guess: `~/miniconda3/envs/mflux/bin`).

## Secrets

Configuration variables and provider API keys can be provided via environment
variables or standard secrets managers (`doppler run --`). Never write secrets into
committed code, or into a command line that lands in a process list or shell history.

`LOCAL_WORKER_TOKEN` is required: the worker exits without it and `spacepilot launch`
refuses to start a billing instance it could not deploy to.

## Tests

```bash
python -m pytest tests/ -q
```

`tests/conftest.py` redirects `SPACEPILOT_OUTPUTS_DIR` to a temp dir before
`spacepilot.web_api` is imported. Keep it that way — the suite used to write
generated clips into the real asset library on every run.

A test that passes against the broken code is not a test. When fixing a bug,
check the new test actually fails against the original behaviour before
believing it.

Before believing any local packaging result, move `build/` and `*.egg-info`
aside. setuptools stages package data into `build/lib/` and caches the file
list in `*.egg-info/SOURCES.txt`, and reuses both — so a stale one ships files
the current `pyproject.toml` no longer asks for. On a tree that has been built
before, every `web/**` glob was once deleted and the wheel came out
byte-identical, which nearly got a real packaging hole reported as
non-reproducible. CI builds from a fresh clone and is not exposed; your laptop
is. The `wheel` fixture in `tests/test_wheel_install.py` now builds from a
filtered copy for this reason — reuse it rather than rolling your own.

## Money and hardware

`spacepilot launch` starts a g6e.2xlarge spot instance at roughly $0.75/hour that
bills until terminated. Never launch one to check something; `spacepilot status`
answers most questions for free.

**Account 842954813809, profile `antigravity-dev-user`, region `us-east-1`.**
Never `katana` (529738799911) or `katana2` (471112666526) — those are Sam's.
Name the profile on every command; never let it fall through to whatever
`AWS_PROFILE` happens to be.

**The G-family Spot quota is 8 vCPU, and g6e.2xlarge is 8 vCPU.** So exactly
one box, with no headroom — the pipeline is serialized by quota, not by design.
Anything that assumes two concurrent workers is wrong until that quota moves.

## Read these before asking

Repo docs were cleared for a rewrite on 2026-08-24 (commit 20bf158). What lives
in the repo now:

- **`docs/design/VISION.md`** — the grand vision, so nobody has to re-explain
  it. Read this first.
- **`docs/design/CONCEPT.md`** — the product thesis: ships / docks / providers,
  the honesty rules, the three words. Read this second.
- **`docs/design/INFERENCE-SURFACE.md`** — the `/v1` routes, the one fit verdict
  every surface repeats, and what each call records.
- **`docs/BUILD-PLAN.md`** — ground truth of what works and the phased work
  list, verified against main with file:line evidence.
- **`docs/DECISION-INBOX.md`** — SpacePilot's open decisions, recreated
  2026-09-02 (#108).
- **`docs/LOCAL-SETUP.md`** — local dev environment setup.
- **`docs/MCP-CLIENTS.md`** — MCP client configuration.
- **`docs/design/RUNTIME-CAPSULES.md`** — runtime capsule design.
- **`docs/design/HARDWARE-LANDSCAPE.md`** — hardware landscape survey.

The old operational docs (AWS.md, INFERENCE.md, PIPELINE-STATE.md) are
archived at `~/code/motionvector/handoffs/` — context only, not current
authority. Their load-bearing facts as of the archive date: the AWS boundary
and quota live in this file above; the inference-provider list is
managed via environment variables or Doppler; and nothing in
`outputs/` was ever a real render. DECISION-INBOX.md was archived in the same
2026-08-24 clearing but was recreated on 2026-09-02 (#108) and is current
again — see the pointer above.

Music generation runs about 25× realtime and spins the fans. A 10s cue is
~4 minutes of full-tilt GPU. Ask before starting long runs.

## Hooks

```bash
tools/install_hooks.sh
```

Once per clone. It points `core.hooksPath` at `.githooks/`, which covers every
worktree of this repo at once.

The one hook regenerates `web/registry.json` when the data behind it moved.
That file is generated and committed — the public page has no server to ask —
so it falls behind `spacepilot/registry/` silently, and the thing that used to
notice was a red CI run on a PR that never touched the registry.
`test_exported_json_matches_the_registry` is still the gate; the hook is what
stops it firing. `--no-verify` skips it when a commit is deliberately
mid-edit.

## Conventions

Every endpoint that spends compute or money takes `X-SpacePilot-Token` via the
`require_token` dependency. Read-only routes stay open. Adding a compute route
without the dependency is a bug; `test_compute_endpoints_all_require_the_token`
walks the list and will fail.

Subprocesses take argv lists. `run_cmd` rejects strings outright so no caller
can reintroduce a shell. Never `shell=True`, never `os.system`.

Anything reaching the filesystem from a request goes through `resolve_output`,
which resolves and then checks containment in `OUTPUTS_DIR`. Anything reaching
`innerHTML` in `web/app.js` goes through `esc()`; there is a regression
test that fails if server data is interpolated raw.

Check subprocess return codes and record real failures. The original code sent
ffmpeg's stderr to `/dev/null` and wrote `"completed"` regardless, which hid
broken renders for weeks.

`outputs/music/` belongs to the BGM template batch. API jobs write to
`outputs/<job_id>.wav` at the root.

## Publishing

The cross-repo rule in `~/code/AGENTS.md` applies: this is a private repo, so
push, open the PR, edit its body, and report the URL. Merging to main still
needs a yes. Saurabh can narrow this for one session or task ("hand me the
command", "park it") and that override lasts only for that session or task.

Destructive commands: state the blast radius next to the command, not just
the intent, and confirm before running.
