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
  interpreter -- give edge0 its own environment, the way `mflux` already
  gets one, rather than installing both into the shared one. `spacepilot
  runtimes install edge0` will show the downgrade and refuse `--yes` alone;
  needs `--allow-downgrade` in a shared env, or install elsewhere.
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

## Arm a flight night, today
As of 2026-09-10, with `mlx-lm`, `whisper-cpp`, and `desert-ant` installed
(edge0 deliberately left uninstalled here -- see above), the flyable set is:
`qwen1-5-moe-a2-7b-chat-4bit`, `qwen3-5-35b-a3b-base-bf16`,
`distil-large-v3-ggml`, and the nine wired Desert Ant variants
(`desert-ant-{voz,clear,ear,uhm,redact,title,clips,emo,gist}-1`).
    caffeinate -s python tools/fly.py queue --max-minutes 240 --while-idle
`fly.py plan` is the live source of truth -- read it before arming, it
reflects whatever is actually installed on the machine you run it on.
