# Working in pluto

Cross-tool agent instructions. `CLAUDE.md` is a symlink to this file, so Claude
Code, Codex, Cursor, Copilot, Antigravity and the rest all read the same rules.
Edit this file, never the symlink.

## Interpreter

The repo carries no `.venv`, and bare `python3` is usually the wrong
interpreter — on the primary dev machine it resolves to base conda, which lacks
fastapi. Use the environment where `requirements.txt` was installed, or set
`PLUTO_PYTHON` / `python_bin` in `.pluto_config.json` (gitignored, machine-local)
and let the CLI resolve it. Anything that imports `spacepilot/web_api.py` —
including pytest — needs that interpreter.

mflux (`spacepilot/drivers/mflux_driver.py`) is a second, separate interpreter on
purpose: installing mflux into the repo env downgrades opencv-python from 5.0
to 4.14, so it lives in its own conda env and is only ever invoked as a
subprocess, never imported. Point the driver at it with `PLUTO_MFLUX_BIN` or
`"mflux_bin_dir"` in `.pluto_config.json` — the bin/ directory of that env
(default guess: `~/miniconda3/envs/mflux/bin`).

## Secrets

Doppler, project `unfoundbox`, config `dev_personal`, scoped at `~/code`. Prefix
with `doppler run --`. Never write secrets into `.env`, into code, or into a
command line that lands in a process list or shell history.

`LOCAL_WORKER_TOKEN` is required: the worker exits without it and `pluto launch`
refuses to start a billing instance it could not deploy to.

## Tests

```bash
python -m pytest tests/ -q
```

`tests/conftest.py` redirects `PLUTO_OUTPUTS_DIR` to a temp dir before
`spacepilot.web_api` is imported. Keep it that way — the suite used to write
generated clips into the real asset library on every run.

A test that passes against the broken code is not a test. When fixing a bug,
check the new test actually fails against the original behaviour before
believing it.

## Money and hardware

`pluto launch` starts a g6e.2xlarge spot instance at roughly $0.75/hour that
bills until terminated. Never launch one to check something; `pluto status`
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

- **`docs/design/CONCEPT.md`** — the product thesis: ships / docks / providers,
  the honesty rules, the three words. Read this first.
- **`docs/BUILD-PLAN.md`** — ground truth of what works and the phased work
  list, verified against main with file:line evidence.

The old operational docs (AWS.md, INFERENCE.md, PIPELINE-STATE.md,
DECISION-INBOX.md) are archived at `~/code/motionvector/handoffs/` — context
only, not current authority. Their load-bearing facts as of the archive date:
the AWS boundary and quota live in this file above; the inference-provider
list is Doppler-scoped (`doppler run --`, project `unfoundbox`); and nothing
in `outputs/` was ever a real render.

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

Every endpoint that spends compute or money takes `X-Pluto-Token` via the
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

Nothing goes to a public or third-party destination — GitHub issues, PRs, PR
descriptions, gists, forums — without Saurabh doing it himself. Draft the text,
hand over the exact command, and say what it exposes: which account it posts
under, what it implies about the work, and that it cannot be retracted. "File
it" approves the content, not the act.

Same shape for destructive commands: state the blast radius next to the command,
not just the intent. A `find … -delete` handed over without its scope named
removed 65 files.
