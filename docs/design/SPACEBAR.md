# SpaceBar

- **Status**: Current
- **Written**: 2026-09-02
- **Design language**: `DESIGN.md` at the repo root. Not `~/code/design.md` — that is MotionVector's.
- **Supersedes**: PR 94's `design-system/` token declaration where the two disagree. See "What PR 94 and 97 still hold".

## The shape

SpaceBar is a voice space that works on a Mac with nothing rented. You talk,
it talks back, either of you can interrupt. The answers come from Apple's
on-device model; the numbers in them come from SpacePilot on the same machine,
so it says "25 GB usable" because something measured it. It lives in the menu
bar because that is where a quick question belongs. It is free.

## The seven states

One state at a time. When two could apply, the one higher in this table wins,
because it is the one the user can act on.

| State | Header | What is shown | What the user can do |
| --- | --- | --- | --- |
| no-mic-permission | "Microphone access is off" | The gap, named. No telemetry, no transcript. | **Open Settings** — deep-links the exact privacy pane |
| offline-daemon | "SpacePilot is not running" | The reason, the sentence "Voice still works. Fleet data does not.", and `spacepilot serve`. No numbers at all. | **Retry** |
| idle | "Ready" | Machine name, backend, headroom, loaded models, SpaceBar's own memory | **Talk** |
| listening | "Listening" | The same, plus what it has heard so far, and a mic-open dot | **Stop** |
| thinking | "Thinking" | The last thing heard; the transcript panel takes a gold hairline | **Stop** |
| speaking | "Speaking" | Heard and said, both | **Talk** — talking over it is the interrupt |
| interrupted | "Stopped" | The reply as far as it got, not erased | **Talk** |

Two rules hold across all seven. **A missing reading is the words "no
reading", never a zero** — the daemon's `vram_usable_known: false` means the
probe could not measure it. And **offline shows no stale numbers**: the panel
empties rather than leave a last good reading on screen looking current.

## What a glance shows, what a click opens

360px, one screen, no scroll.

| Zone | Carries | Why there |
| --- | --- | --- |
| Header | state dot + one word | The only thing you need at a glance |
| Machine card | name, backend, headroom, loaded models, SpaceBar's memory rail | The answer to "can I run this here", which is the question |
| Transcript | last thing heard, last thing said | Two lines. Not a chat log — a chat log in a popover is a worse chat log |
| Controls | one verb, mic-open indicator, Quit | One button. The verb changes with the state; the button does not move |

The glyph is a template image, so macOS tints it for the bar it sits on.

No fleet view. `spacepilot_get_fleet_status` was deleted from the MCP server
for returning a fixed ten-instance fleet that does not exist. SpaceBar shows
one machine because there is one machine.

## Brains

Two implementations of one `Brain` protocol answer `Talk`. `AppleBrain`
(`AppleFoundationModelManager`) is unchanged: `SystemLanguageModel.default`,
on device, free. `DaemonBrain` sends the same system instructions and the
same telemetry block to the daemon's `POST /v1/chat/completions` instead —
`docs/design/INFERENCE-SURFACE.md` is the wire shape. Neither fabricates: a
brain that cannot answer throws a `BrainError` and the popover says why,
never a plausible-looking reply.

**Choosing one.** Launch arguments win, then whatever was picked last
session, then Apple:

```
SpaceBar --brain apple
SpaceBar --brain daemon --model qwen3-8-27b-4bit
SpaceBar --brain daemon                              # auto-picks a model
```

With `--brain daemon` and no `--model`, `DaemonBrain` asks `GET /v1/models`
and takes the first variant that is both `kind: text` and `verdict.level:
runs_well` **and** `served: true` — `runs_well` alone still lists variants
with no wired route, which would 409 on every question. `--model
claude-sonnet-5` works the same way as any other id: it has to be in the
listing, which only happens when the daemon has `ANTHROPIC_API_KEY` set —
see INFERENCE-SURFACE.md's "Remote providers".

The choice persists in `UserDefaults`, and the Diagnostics disclosure carries
a picker — three fixed choices (Apple Intelligence, daemon auto, daemon
`claude-sonnet-5`) plus whatever is active right now, so an explicit
`--model` still shows correctly even when it is not one of the three.
Switching takes effect on the next question.

**What each needs.** Apple: Apple Intelligence turned on; if it is off,
`Talk` says so instead of thinking. Daemon: the daemon up on
`127.0.0.1:8088` and, for a local model, its weights actually cached —
`served: true` on `/v1/models` means the route is wired, not that the
weights are downloaded. Three failure sentences, none of them invented: the
daemon unreachable renders the existing `offline-daemon` state and says "I
can't answer with the daemon brain"; a requested model not in the listing
names the ones that are; anything else the daemon refuses with (weights not
cached, a driver error) is read back in the daemon's own words.

`--self-test <wav>` takes the same two flags, so the daemon path can be
proven with no microphone in it — see `docs/LOCAL-TEST.md`.

## Voice to cockpit

The daemon is FastAPI on `127.0.0.1:8088`. The token comes from
`GET /api/token`, which answers loopback callers only — the path `web/app.js`
already takes. There is no env var for it; `LOCAL_WORKER_TOKEN` is the remote
worker's credential, a different secret.

**The rule is an allowlist, not a method.** "Voice can do GETs" is wrong
twice: some token-gated routes are GETs, some ungated routes are POSTs that
write files.

| Tier | Reachable by voice | Endpoints |
| --- | --- | --- |
| Read, no confirmation | yes | `/healthz`, `/api/compute/local-status`, `/api/compute/local-profile`, `/api/compute/compatibility`, `/api/runtimes`, `/api/measurements`, `/api/summary`, `/api/assets` |
| Read, expensive | yes, on request only | `/api/cockpit/status` — shells out to `aws ec2 describe-instances` behind a 2s cache. Never polled |
| Spends compute | spoken confirmation | `/api/generate*`, `/api/upscale-4k`, `/api/generate/music`, `/api/generate/voice`, `/api/compute/recipes/{id}/download` |
| Spends money | spoken confirmation, cost read back first | `/api/gpu/launch`, `/api/gpu/terminate` — both also demand `{"confirm": true}` server-side |
| Never | no | `/api/gpu/inspect/shell`, `/api/runtimes/{id}/install`, `/api/checkpoints/restore/*`, `/api/cockpit/config` |

A spoken confirmation is: SpaceBar says the price and the verb, then waits
for a word. No timeout default. Silence cancels.

Of the 17 MCP tools, 11 are read-only and sit in tier 1. The six that are not
— `create_checkpoint`, `restore_checkpoint`, `download_model_recipe`,
`train_lora`, `decompose_storyboard`, `install_runtime` — are tier 3, and
`install_runtime` is tier 5 because it mutates the Python environment.

**The fleet vocabulary is not on 8088.** `/v1/fleet`, `/v1/orders`, `/v1/run`
belong to a second daemon (`spacepilot daemon run`) speaking over a Unix
socket, not mounted into this app. "Fleet" here means one machine.

## The local-first ladder, as it applies here

| Rung | What runs | Cost | State today |
| --- | --- | --- | --- |
| 0 | Speech to text — `SFSpeechRecognizer` with `requiresOnDeviceRecognition` | free | works |
| 0 | Text to speech — `AVSpeechSynthesizer` | free | works |
| 1 | The answer — `SystemLanguageModel.default`, ~3B on device | free | works |
| 2 | Bigger open models through CoreAI/CoreML | free, slower | not built |
| 3 | A rented box | ~$0.75/hr | reachable, gated |

The app never climbs a rung on its own. Rung 3 costs money, and money is loud.

## First launch, and what he will be asked

Traced through the code. Nothing is requested at launch — the app draws its
glyph and polls the daemon. Two dialogs appear on the **first press of
Talk**:

1. **Speech Recognition** — `SFSpeechRecognizer.requestAuthorization`. macOS shows the `NSSpeechRecognitionUsageDescription` string.
2. **Microphone** — `AVCaptureDevice.requestAccess(for: .audio)`, only if step 1 was granted. Shows `NSMicrophoneUsageDescription`.

Deny either and the popover moves to no-mic-permission and offers the deep
link rather than failing silently. Both strings were rewritten this pass: they
promised "sovereign voice pair-programming", and the speech one implied
on-device processing the code never requested. It requests it now.

## Milestones

| # | Ships | Acceptance test |
| --- | --- | --- |
| M1 | Real transport, seven states, no invented numbers | With the daemon up, the popover shows this machine's real backend and headroom; with it down, it says so and shows nothing else |
| M2 | Push-to-talk and the cost gate | A spoken request for a dock reads back "$0.75 an hour" and does nothing until a word confirms it |
| M3 | Tools — the model reaches the daemon itself, via `FoundationModels` `Tool` | "What can I run here?" is answered from a live `/api/compute/compatibility` call the model made, not from injected text |
| M4 | App Intents — Siri, Shortcuts, Spotlight, Control Center | "Hey Siri, what's my headroom" answers with no SpaceBar window open and no model call |

M1 is done as of this branch.

## Ideas

Five things not built, each of which would make a Mac user pay.

**1. The meter in the menu bar.** While a rented box bills, the glyph becomes
a running cost — `$0.42`, ticking, next to the clock. Click it: the only
button is Terminate, with the total so far. One g6e forgotten overnight is $6,
more than a year of the subscription. It pays for itself the first time.

**2. Hold to talk.** No wake word, no always-listening. Hold a chord anywhere
on the Mac, talk, release. The mic dot is driven by the audio graph, so "is it
listening" is answerable by looking. Every Mac voice assistant today is either
always on or needs you to say something out loud in an office.

**3. "What happened while I was out?"** A local rolling log of runs, thermal
excursions and failures, summarized on-device on the first click of the day:
*"Two renders finished, one failed on frame 340, throttled 20 minutes around
2pm."* A dashboard you would otherwise open, in the two seconds you have.

**4. "Can this Mac do it?"** Name a model out loud. It answers from
`/api/compute/compatibility` — measured headroom now, not the spec sheet — and
if the answer is no it says what renting costs in the same breath. SpacePilot's
thesis with the terminal removed.

**5. The verbs become Shortcuts.** Every tier-1 verb is also an App Intent, so
it works from Siri, Spotlight, a Shortcut and a Control Center button, with no
model call and no cost, because Apple Intelligence does the understanding.
Purge VRAM as a Control Center toggle. The app disappears into the OS.

## What is not good today, and the fix

| Problem | Fix | Size |
| --- | --- | --- |
| The popover's numbers were decoration — `41°C`, `0 RPM`, `25.0/32.0 GB` hardcoded, `ship=m1max` passed to the model as a literal | Read the machine; say "no reading" when we cannot | done |
| A websocket to `ws://127.0.0.1:8090` was opened and never used; nothing listens there | HTTP to 8088, token from `/api/token` | done |
| Colours lived in two places and had already drifted | `tokens.css` generates `Tokens.swift`; `--check` fails on drift | done |
| `gen_tokens.py --check` is not wired into CI, so drift is still possible | One step in the existing workflow | ~5k |
| No push-to-talk — the mic stays open for a whole session | A global hotkey and a held-key audio graph | ~40k |
| No cost gate. A spoken "launch a dock" would go straight through | The confirmation tier above, plus the menu bar meter | ~60k |
| The model gets telemetry injected as text and has no tools, so it can only discuss what we pre-fetched | `FoundationModels` `Tool` bridging to the tier-1 allowlist | ~90k |
| No App Intents at all, so Siri and Shortcuts cannot reach any of it | Four read-only intents first | ~70k |
| Nothing on the Swift side is tested | Snapshot the seven states; assert the daemon client's offline path | ~35k |
| `/api/cockpit/status` reports `region` and `instance_type` from hardcoded fallbacks whose keys never match the real config | One-line key fix in `gpu.py`; it reports `g6e.xlarge` for a `g6e.2xlarge` fleet | ~5k |

## What PR 94 and 97 still hold

PR 97 is this branch's base, merged in. PR 94's foundations remain the source
for gold, silver, agent and chrome, which `DESIGN.md` does not define. What
does not survive is PR 94's claim that gold and silver outrank everything:
`DESIGN.md` is the authority and won on fonts and on the failure colour. PR 94's
mockups have no script and hardcoded numbers — layout references, not a
running surface.
