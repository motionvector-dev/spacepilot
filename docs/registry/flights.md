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
and Desert Ant Labs have no runtime registered in this repo yet, so those
entries stay blocked with no fix command until one is added.
