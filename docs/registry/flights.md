# Flying the patient models

`tools/fly.py` measures registered-but-unflown registry variants, one at a
time, unattended, and writes their real numbers back into the registry.
Every guard refuses rather than assumes; `--dry-run` (the default for
`fly.py run`) never touches the network, the registry, or git.

## Arm a flight night
    caffeinate -s python tools/fly.py queue --max-minutes 240 --while-idle

`queue` checks, before every model, that the machine has been idle 10+
minutes (`ioreg -c IOHIDSystem`'s `HIDIdleTime`) and the display is asleep
or locked (`IODisplayWrangler`'s `CurrentPowerState`). Keyboard/mouse
activity stops it immediately, between models only.

## What it measures
Per unflown variant, smallest download first: disk guard (refuses if free
space after the download drops under 40 GB), power guard (`pmset -g batt`
must say AC Power), pinned SHA only (never `main`), then cold load time,
3x tok/s over a fixed 128-token prompt, and peak memory -- plus Gate 3
typed-task pass rate for `role: executor` models (when
`mvec-engine/benchmarks/l2r/` exists on the engine's main), realtime factor
over a fixed 30s WAV for STT/audio roles, and WER against a known transcript
for Voz.

## Where the log goes
One JSON line per model -- start, end, outcome -- to
`~/code/motionvector/media-scratch/flights/<date>/flight-log.jsonl`.
Downloaded weights are deleted after measuring unless `--keep`.

## How a flight becomes a registry PR
`fly.py run <model-id> --fly-for-real` commits one measurement on
`flight/<model-id>-<date>`, in the registry's own `speed:`/`working_set:`
shape (`source: measured`), nothing else touched. `--push` pushes; nothing
pushes on its own, and `fly.py` never opens the PR -- read the log, then
open it by hand.

## Runtime gaps
`fly.py plan` marks any entry `BLOCKED` when its runtime is not installed,
naming the fix (`spacepilot runtimes install <id>`) where one exists. CoreAI
(muse-glimmer) has no runtime registered in this repo yet, so it stays
blocked with no fix command.

## Runtimes: edge0 and desert-ant
Registered 2026-09-10 (`spacepilot/registry/runtimes/edge0.yaml`,
`spacepilot/registry/runtimes/desert-ant.yaml`):

- **edge0** -- pip, from git, pinned to a commit SHA on Edge0-AI/edge0 (no
  PyPI release exists): `pip install "edge0 @
  git+https://github.com/Edge0-AI/edge0.git@fbab5f8c08e843e204c0fc6ae18b89a154c652cf"`.
  Runs `edge0-35b-a3b-preview` and `edge0-8b-a1b-preview` -- plain `mlx-lm`
  cannot run an Edge0 checkpoint correctly (no SSD expert streaming, no
  prerouter, no Recover-LoRA), which is what the earlier `mlx-lm`-routed
  manifests got wrong. Pins `mlx-lm==0.31.0` exactly, which downgrades this
  registry's own `mlx-lm>=0.31.3` runtime if installed into the same
  interpreter.

  **edge0 is flyable now** -- `spacepilot/registry/runtimes/edge0.yaml` sets
  `install.isolated: true`, a new flag `spacepilot/runtimes.py` reads for any
  pip runtime that needs its own environment instead of this project's
  shared interpreter. `spacepilot runtimes install edge0` creates a venv at
  `spacepilot.paths.runtime_env_dir("edge0")` (`$SPACEPILOT_DATA_DIR
  /runtime-envs/edge0`, or `~/Library/Application Support/spacepilot
  /runtime-envs/edge0` on macOS with no override; `$SPACEPILOT_RUNTIME_ENVS_DIR`
  overrides the whole root) and pip installs the pinned git SHA into it --
  no downgrade prompt, no `--allow-downgrade`, because the shared
  interpreter is never touched. `spacepilot runtimes check edge0` and
  `tools/fly.py plan` both resolve the isolated venv's own interpreter to
  decide "installed", the same way an mflux check resolves its conda env
  without importing mflux into this process. This is the same shape mflux
  already uses (see `spacepilot/drivers/mflux_driver.py`) but managed by
  this project instead of a hand-created conda env -- mflux predates the
  `isolated` flag and still runs through its own
  `_EXTERNAL_ENTRY_POINT`/`SPACEPILOT_MFLUX_BIN` route.

  Installed and verified 2026-09-10 in the isolated venv: `edge0` 0.1.0
  (`import edge0` and `from edge0 import AutoEngine` both clean), `mlx`
  0.30.4, `mlx-metal` 0.30.4, `mlx-lm` 0.31.0 exactly as pinned (pip does
  warn this release is yanked on PyPI for a KV-cache batching bug -- see the
  recipe's notes; not fixed here, upstream edge0's problem). The project's
  own shared-interpreter `mlx-lm` was never touched -- confirmed by `pip
  freeze` against the shared interpreter still showing no `mlx-lm` at all.
- **desert-ant** -- a new `script` install method (not pip): the CLI
  (Desert-Ant-Labs/desert-ant-cli, MIT) is a Swift binary, released as a
  signed tarball, with no PyPI or npm package at all. Installed from the
  pinned `v0.1.1` release's `install.sh`, verified by shelling out to
  `desertant --version`, never imported. Runs nine of the twelve registered
  Desert Ant manifests (voz, clear, ear, uhm, redact, title, clips, emo,
  gist); align and shapes are excluded by the CLI itself (see the recipe's
  notes) and tongue has no CLI adapter at all -- all three stay `BLOCKED`
  with no fix, on purpose, not stubbed. None of the twelve needs an account
  or an API key.

## Gate 3 for executors: pulling benchmarks/l2r from the engine repo
Gate 3 (the L2R typed-task semantic-range pass rate) lives in the engine
repo, not this one: `benchmarks/l2r/` at motionvector-dev/motionvector
(local checkout `~/code/motionvector/mvec-engine`). A prior lane reported it
"missing" because it looked at the local checkout, which sits on a feature
branch -- the benchmark exists on the engine's own `origin/main`
(`git -C ~/code/motionvector/mvec-engine ls-tree origin/main benchmarks/l2r/`
lists `REPORT.md`, `gate3_semantic.py`, `fixture.py`, `tasks.py`, `data/`).

`tools/fly.py run <model-id>` now takes `--engine-ref` (default
`origin/main`, never a local feature branch) and, for any `role: executor`
entry (`FlightPlan.needs_gate3`), materialises `benchmarks/l2r/` from that
ref with `git archive <ref> benchmarks/l2r | tar -x` into the flight's
scratch dir (`~/code/motionvector/media-scratch/flights/gate3-scratch
/<model-id>/`) -- a plain archive extraction, never `git worktree add`, so
it never touches the engine checkout's own working tree. In `--dry-run`
(the default) this only logs the archive command and the Gate 3 command it
would run; nothing is extracted and no subprocess runs
(`fly.DryRunGate3Extractor`). `--fly-for-real` extracts for real
(`fly.GitArchiveGate3Extractor`) before running the benchmark.

Per `benchmarks/l2r/REPORT.md`'s own Gate 3 section, the command is:

    MVEC_BIN=<mvec binary> <python> gate3_semantic.py --model <model under test>

run with the working directory set to the extracted `benchmarks/l2r/`
itself -- `gate3_semantic.py` imports its sibling modules (`l2r_codecs`,
`fixture`) by bare name, so it has to run from inside that directory, not
this repo's root or the engine repo's root. `tools.fly.gate3_command()`
builds this argv; `tools.fly.resolve_mvec_bin()` finds the binary, checking
(in order) `~/.local/bin/mvec` then
`~/code/motionvector/.cargo-target/release/mvec`, and reports neither
found rather than building one -- cargo builds are heavy work and stay off
this machine (the fan rule).

**On this Mac, checked 2026-09-10**: both candidates exist and are
identical (`mvec 0.1.0`, commit `a004338a`, same sha256) --
`~/.local/bin/mvec` is NOT stale here; an earlier note from 2026-09-08 said
it lacked the 3D schema, but both binaries were rebuilt fresh today and both
strings-match `camera3d`/`light3d`. `resolve_mvec_bin()` picks
`~/.local/bin/mvec` first. A real Gate 3 run was not executed as part of
this change -- it needs a live model loaded for inference, out of scope
here (no model downloads, no inference) -- only the archive-and-command
plumbing, exercised end to end in `--dry-run` and tested against a faked
engine repo (`tests/test_fly_gate3.py`).

Dry-run example (edge0-35b-a3b-preview-4bit, role=executor):

    gate3 command (cwd=.../gate3-scratch/edge0-35b-a3b-preview/benchmarks/l2r):
    MVEC_BIN=/Users/saurabh/.local/bin/mvec /path/to/python
    .../benchmarks/l2r/gate3_semantic.py --model edge0-35b-a3b-preview-4bit

## Arm a flight night, today
Checked directly against `spacepilot runtimes check` on this Mac,
2026-09-10 (`fly.py plan` is the live source of truth -- this is one
snapshot of it, not a standing claim): `desert-ant` and, as of this change,
`edge0` (its own isolated venv -- see above) are installed; `mlx-lm` and
`whisper-cpp` are **not** installed on this interpreter right now (a
previous note in this doc claimed otherwise -- re-checked, corrected here).
The currently flyable set is therefore `edge0-8b-a1b-preview-4bit`,
`edge0-35b-a3b-preview-4bit`, and the nine wired Desert Ant variants
(`desert-ant-{voz,clear,ear,uhm,redact,title,clips,emo,gist}-1`);
`qwen1-5-moe-a2-7b-chat-4bit`, `qwen3-5-35b-a3b-base-bf16`, and
`distil-large-v3-ggml` stay `BLOCKED` until `spacepilot runtimes install
mlx-lm` / `whisper-cpp` is run on this machine.
    caffeinate -s python tools/fly.py queue --max-minutes 240 --while-idle
`fly.py plan` is the live source of truth -- read it before arming, it
reflects whatever is actually installed on the machine you run it on.
