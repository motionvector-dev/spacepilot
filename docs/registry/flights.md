# Flying the patient models

`tools/fly.py` measures registered-but-unflown registry variants, one at a
time, unattended, and writes their real numbers back into the registry.
Every guard refuses rather than assumes; `--dry-run` (the default for both
`fly.py run` and `fly.py queue`) never touches the network, the registry,
or git.

## Arm a flight night, the one command
Read the briefing first, then type this and walk away:

    python tools/fly.py plan --tonight
    caffeinate -s python tools/fly.py queue --max-minutes 300 --while-idle --fly-for-real --push

`plan --tonight` prints the exact order `queue` will fly tonight (same as
plain `plan`), plus the briefing: total download, the single largest
peak-memory estimate, how many entries are still BLOCKED and how many of
those the pre-flight phase will install for you, whether power will be
measured tonight and via which source (with the optional sudoers line for
`powermetrics` -- see "Power" below), where the flight log lands, and the
branch shape each flown model gets committed on.

`queue` (like `run`) is `--dry-run` by default -- add `--fly-for-real` to
actually install missing runtimes, download, measure, write, and commit,
all night, unattended. `--push` pushes each flight branch as it lands;
without it every branch stays local. Before every model (and before every
pre-flight install -- see "Pre-flight: installing missing runtimes at
night" below) `queue` checks that the machine has been idle 10+ minutes
(`ioreg -c IOHIDSystem`'s `HIDIdleTime`) and the display is asleep or locked
(`IODisplayWrangler`'s `CurrentPowerState`), plus the same disk and
AC-power guards a single `run` checks. Keyboard/mouse activity stops it
immediately, between models only. A demo dry-run on a machine that is not
actually idle or on AC can force every guard green with `--force-guards`
(refused together with `--fly-for-real` -- it exists for the paste-into-a-
PR-body dry-run below, never for a real night).

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

## Power

Every real flight now brackets its run with a power sample and records it
alongside tok/s and peak memory, producing joules per generated token for
executor/transducer/base roles, joules per second of audio for STT/audio
roles, and joules per classified item for pii/lang-id/drafter/utility roles
(`tools/fly.py`'s `ROLE_ENERGY_METRIC`, `spacepilot.model_registry.
SPEED_METRICS`'s three `joules_per_*` entries).

Two sources, tried in order, both probed on this Mac 2026-09-10:

- **`powermetrics`** needs root. Measured directly: `powermetrics -n 1 -i
  1000 --samplers cpu_power` exits 0 but prints "powermetrics must be
  invoked as the superuser" and samples nothing. `sudo` is not available in
  this environment, so this source is not usable here today --
  `check_powermetrics_unprivileged` reads the output text (not just the
  exit code) so a future machine where it genuinely works unprivileged
  (root, or an entitled/setuid build) takes this branch automatically.
- **`ioreg -rn AppleSmartBattery`** worked unprivileged in the same
  session. `InstantAmperage` and `Voltage` are both unsigned 64-bit fields;
  a discharging battery's current comes back as two's-complement (measured
  here: `18446744073709550034` == `2**64 - 1582`, i.e. -1582 mA at 11441
  mV, ~18.1 W). This only has a number while genuinely running on battery
  -- a desktop Mac, or a laptop on AC power, has no discharge current for
  this field to report.

**On this Mac, right now: `ioreg-battery` is the working unprivileged
source, `powermetrics` is not.** `sample_power()` (`tools/fly.py`) tries
powermetrics first and falls back automatically; when neither source has a
number (AC power, or a desktop with no battery) it returns
`available=False` with the reason, and the flight's power fields are
written as unmeasured rather than a fabricated zero.

**Limits, stated plainly**: the `ioreg-battery` reading is instantaneous
system-wide battery draw, not this process's own draw -- it cannot
separate the flight's power from whatever else is running, and it says
nothing on AC power. `powermetrics`'s CPU-package number (when available)
is CPU power only, not full-system. Every `joules_per_*` speed entry
carries `power_source` and `power_limits` alongside the number so a reader
sees which source produced it and what that source cannot see (see
`spacepilot.model_registry.Speed`).

A dry run (`fly.py run <model-id>`, the default) stops before sampling
anything and says so in its own step log: `power: unmeasured (dry-run
stops before sampling)`.

## Runtime gaps
`fly.py plan` marks any entry `BLOCKED` when its runtime is not installed,
naming the fix (`spacepilot runtimes install <id>`) where one exists. CoreAI
(muse-glimmer) has no runtime registered in this repo yet, so it stays
blocked with no fix command.

## One truth for where a runtime lives
Fixed 2026-09-11. `fly.py plan` and `spacepilot runtimes list` used to be
able to disagree about the same shared-interpreter runtime: both resolve
`spacepilot.runtimes.interpreter()`, which fell back to `sys.executable` --
the interpreter of whichever process happens to import the module. That is
the pipx-installed `spacepilot` console script's own venv by accident when
`spacepilot runtimes list` runs it, but *not* the interpreter `fly.py` runs
under when launched the documented way (`python tools/fly.py ...`, the
ambient interpreter) -- and not the interpreter `spacepilot run <cli>`
actually subprocesses into at flight time either. A shared-interpreter
recipe (`mlx-lm`, `whisper-cpp`) installed into one and checked against the
other reads as missing even though the package is right there -- this is
exactly the PR #137 story: that lane's own report said both were installed,
because it checked against `local-ml-py311`, a third interpreter neither
`fly.py` nor the real `spacepilot run` command ever uses.

`interpreter()` now resolves the pipx console script's own interpreter
directly (`_spacepilot_console_python()`, reading the `exec '<python>' "$0"
"$@"` line out of the installed `spacepilot` shim) whenever no explicit
override (`SPACEPILOT_PYTHON`/`PLUTO_PYTHON`, or a configured `python_bin`)
is set, before ever falling back to `sys.executable`. Both callers now
resolve the identical path regardless of which process asks --
`tests/test_runtimes.py`'s interpreter-truth tests prove it with a faked
shim, never a real one.

`mlx-lm` (0.31.3) and `whisper-cpp`/`pywhispercpp` (1.5.1) are installed
into that exact interpreter now (`pipx runpip spacepilot install
"mlx-lm>=0.31.3" "transformers>=5.12.1,<5.13" "pywhispercpp>=1.5.1"` --
pipx strips pip from its own managed venvs, so `pip` itself has to go
through `pipx runpip <app>`, not a bare `python -m pip`). `spacepilot
runtimes list` and `fly.py plan` agree on both now -- checked directly
against each other, not asserted:

| runtime | env | installed |
| --- | --- | --- |
| mlx-lm | pipx spacepilot venv (shared interpreter) | yes -- 0.31.3 |
| whisper-cpp | pipx spacepilot venv (shared interpreter) | yes -- 1.5.1 |
| edge0 | its own isolated venv (`install.isolated: true`) | yes -- 0.1.0 |
| desert-ant | `desertant` CLI on PATH (script install) | yes |
| bitnet-cpp | `bitnet-cli` on PATH (script install, CMake build) | no -- see Pre-flight below |
| llama-cpp-prism | `llama-cli-prism` on PATH (script install, CMake build) | no -- see Pre-flight below |
| muse-glimmer (CoreAI) | no runtime registered in this repo yet | n/a -- no fix command |

## Pre-flight: installing missing runtimes at night
`fly.py queue`'s pre-flight phase (added alongside the interpreter fix
above) runs before any flight: for every distinct runtime a planned model
needs and does not have, it installs that runtime once -- in plan order,
under the exact same idle/AC-power/disk guards a flight itself checks --
and logs the attempt to the same `flight-log.jsonl`, keyed by `runtime_id`
instead of `model_id`, with its duration. This is what actually makes
`bitnet-cpp` and `llama-cpp-prism` flyable overnight: both stayed
BLOCKED-with-a-fix-command rather than run as a several-minute CMake source
build on a MacBook when their recipes were registered (see those recipes'
own notes) -- the pre-flight phase is where that build now happens, nightly,
unattended, `nice -n 19` and bounded to a handful of parallel jobs
(`CMAKE_BUILD_PARALLEL_LEVEL`/`MAKEFLAGS`) so it never fights the rest of
the machine for cores, the same posture quietcargo/quietpnpm take for Rust
builds elsewhere in this fleet.

A guard failure (idle, AC power, disk) during pre-flight stops the whole
night, exactly like it always has for a flight -- it is not scoped to one
runtime. A failed *install itself* (the command ran and lost) is scoped:
only the models that needed that runtime are marked `skipped: install
failed`, carrying the tail of the install log, and the night continues to
every other model. `--dry-run` (the default) logs every install command it
would run -- `nice -n 19` prefix, bounded job env, the exact `curl | sh` or
pip target -- and touches no network, no filesystem, no subprocess; tested
against faked installers and faked guards in `tests/test_fly.py` (see the
"queue: pre-flight installs" section there), never a real bitnet.cpp or
PrismML build.

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
Checked directly against `spacepilot runtimes list` and `fly.py plan` on
this Mac, 2026-09-11, now that both agree on the same interpreter (see "One
truth for where a runtime lives" above) -- this is one snapshot, not a
standing claim; `fly.py plan` is always the live source of truth, read it
before arming.

`desert-ant`, `edge0` (its own isolated venv), `mlx-lm` (0.31.3), and
`whisper-cpp` (1.5.1) are all installed. The flyable set is every entry
`plan` prints with no `BLOCKED` flag -- that now includes
`qwen1-5-moe-a2-7b-chat-4bit`, `qwen3-5-35b-a3b-base-bf16`, and
`distil-large-v3-ggml`, alongside Edge0 and the nine wired Desert Ant
variants. `bitnet-b1-58-2b4t-{packed,gguf-i2s}` stay `BLOCKED` in a plain
`plan` listing, but are no longer stuck: `queue`'s pre-flight phase builds
`bitnet-cpp` for them automatically (see "Pre-flight" above) -- the only
entries that stay blocked with no fix at all are the ones with no runtime
registered in this repo yet (CoreAI, and the Desert Ant models the CLI
itself excludes).

    python tools/fly.py plan --tonight
    caffeinate -s python tools/fly.py queue --max-minutes 300 --while-idle --fly-for-real --push
