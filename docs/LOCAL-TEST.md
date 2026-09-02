# Running SpaceBar on this Mac

- **Status**: Current
- **Written**: 2026-09-02

## One command

```bash
native/SpaceBar/tools/make_app.sh
```

It builds release, checks the Info.plist, assembles `SpaceBar.app`, ad-hoc
signs it with the entitlements, and prints the `open` command to run.

SpaceBar is `LSUIElement`, so there is no Dock icon and no window. Look for the
ship glyph in the menu bar.

## What macOS will ask, and when

Nothing at launch. Two dialogs on the **first press of Talk**, in this order:

| # | Dialog | Comes from | Deny it and you get |
| --- | --- | --- | --- |
| 1 | Speech Recognition | `SFSpeechRecognizer.requestAuthorization` | "Speech recognition is off" + Open Settings |
| 2 | Microphone | `AVCaptureDevice.requestAccess(for: .audio)` | "Microphone access is off" + Open Settings |

Both are macOS's own dialogs. Neither is skippable and neither can be granted
from a script. Answering them is the only manual step.

Apple Intelligence is separate. With it off, SpaceBar still listens and still
transcribes — it just answers "Apple Intelligence is off, so there is no
on-device model to answer with" instead of thinking. Nothing crashes.

## `swift run` does not work, on purpose

```
$ swift run SpaceBar
SpaceBar cannot run as a bare executable.
...
```

A SwiftPM executable is a bare Mach-O with no Info.plist. macOS SIGABRTs any
process that reads a speech or microphone status without one — TCC namespace,
"attempted to access privacy-sensitive data without a usage description". The
app cannot catch that, so it checks `Bundle.main` at startup and exits 64 with
the fix instead of dying.

## Testing the voice path with no microphone

```bash
swift build && .build/debug/SpaceBar --dry-run-voice
```

Runs the whole talk path — status read, both authorization requests, the audio
graph entry, teardown — against five stubbed permission answers, and exits
non-zero if any of them fails to land in the right state. It touches no
microphone, opens no System Settings, and speaks nothing aloud.

```
dry-run-voice: denied → Speech recognition is off
dry-run-voice: restricted → Speech recognition is off
dry-run-voice: microphone-denied → Microphone access is off
dry-run-voice: microphone-restricted → Microphone access is off
dry-run-voice: granted → Listening
dry-run-voice: ok — 5 permission paths, no crash
```

## Proving Talk works with no microphone

```bash
.build/SpaceBar.app/Contents/MacOS/SpaceBar --self-test path/to/clip.wav
```

Runs the same recogniser, on-device model, and synthesiser Talk uses — file
input instead of a live mic tap — and times each stage. It still asks for
Speech Recognition (the same TCC call Talk makes) but never touches
`AVAudioEngine` or `AVCaptureDevice`, so a failure here is never a microphone
or audio-device problem. Make a test clip with macOS's own TTS, no mic
involved:

```bash
say -o clip.wav --data-format=LEI16@16000 "what can this mac run"
```

## Screenshots of the seven states

```bash
.build/SpaceBar.app/Contents/MacOS/SpaceBar --snapshot /tmp/spacebar-shots
```

Renders the real popover offscreen in every state, in both themes. No window
server, no permission.

## The build gate

`make_app.sh` fails the build if any voice callback is main-actor-isolated.

Under Swift 6, a closure written inside a `@MainActor` method and handed to an
Objective-C completion handler is inferred main-actor-isolated, and the
compiler emits a runtime executor check at its entry. `requestAuthorization`
calls back on TCC's XPC queue, so that check fails and the process takes
SIGTRAP before the handler's first line — the ten crash reports from
2026-08-28. The callbacks now live in `nonisolated` methods; the gate scans the
built binary and fails if one moves back.

## Durable restarts (2026-09-02, later the same day)

The daemon and the cockpit now run under mvec-local from the clean main
worktree, so they survive agent sessions and reboots:

```bash
mvec-local stable start spacepilot --apply   # daemon, 127.0.0.1:8088, doppler-wrapped
mvec-local stable start cockpit --apply      # React cockpit, http://127.0.0.1:5173/cockpit
mvec-local status
```

After a merge to main: `mvec-local main sync spacepilot --apply`, then restart
both. SpaceBar: from the clean main worktree,
`~/code/.mvec-local/worktrees/main/spacepilot/native/SpaceBar/tools/make_app.sh`

## Choosing the brain

`SpaceBar` and `--self-test` both take `--brain apple|daemon` and, for the
daemon brain, `--model <id>`. Apple is the default and needs nothing beyond
Apple Intelligence being on. The daemon brain needs the daemon up on
`127.0.0.1:8088`:

```bash
open "$APP" --args --brain apple
open "$APP" --args --brain daemon --model qwen3-8-27b-4bit
```

Omit `--model` and it auto-picks the first `runs_well`, served text model
from `GET /v1/models`. The choice persists in `UserDefaults`, so a plain
`open "$APP"` after either of the above remembers it; the Diagnostics
disclosure has a picker for switching without a relaunch. See
`docs/design/SPACEBAR.md`, "Brains".

## Every mlx-lm text variant, not just the default

`/v1/chat/completions` serves every text variant the mlx-lm runtime declares
it runs (`spacepilot/registry/runtimes/mlx-lm.yaml`, `runs:`), not only
`qwen3-8-27b-4bit`. `GET /v1/models` lists each one with `x_spacepilot.served:
true`; this proves the smaller Qwen1.5 MoE variant answers the same route:

```bash
curl -sS http://127.0.0.1:8088/v1/chat/completions \
  -H "X-SpacePilot-Token: $(cat .studio_token)" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen1-5-moe-a2-7b-chat-4bit", "messages": [{"role": "user", "content": "Say hi in five words."}], "max_tokens": 20}'
```

`spacepilot run text --model qwen1-5-moe-a2-7b-chat-4bit --prompt "..." --yes`
runs the same variant from the CLI; omit `--model` and it prints and uses the
first served text variant instead.

## Testing against Claude instead of a local model

`claude-sonnet-5` is a second backend behind `/v1/chat/completions` — see
`docs/design/INFERENCE-SURFACE.md`, "Remote providers" — for testing
SpaceBar's brain while Apple Intelligence is off, or while the local rungs
are not wired yet. `ANTHROPIC_API_KEY` comes from Doppler
(`unfoundbox`/`dev_personal`), never from a file in the repo:

```bash
doppler run --project unfoundbox --config dev_personal -- \
  curl -sS http://127.0.0.1:8088/v1/chat/completions \
    -H "X-SpacePilot-Token: $(cat .studio_token)" \
    -H "Content-Type: application/json" \
    -d '{"model": "claude-sonnet-5", "messages": [{"role": "user", "content": "Say hi in five words."}]}'
```

`GET /v1/models` lists `claude-sonnet-5` only when the key is present in the
daemon's own environment, so start the daemon itself under `doppler run --`
if it is not already — `X-SpacePilot-Token` still gates the POST regardless.
then the `open` line it prints.
