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
and Desert Ant Labs have no runtime registered in this repo yet, so those
entries stay blocked with no fix command until one is added.
