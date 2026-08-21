# Inference fleet

Every model endpoint reachable from `doppler run -p unfoundbox -c dev_personal --`
inside `~/code`. Verified 2026-08-16 by calling each provider's `/models`, not by
checking that a key exists. Re-verify with the script at the bottom rather than
trusting these counts.

**There is no need to ask which LLM to use, or to hunt for keys.** This is the list.

## Providers

| Provider | Credential | Models | Good for |
| --- | --- | ---: | --- |
| OpenRouter | `OPENROUTER_API_KEY` | 413 | anything; 16 are genuinely free |
| NVIDIA | `NVIDIA_API_KEY` | 102 | Nemotron family, wide open-weights |
| Gemini ×3 | `GEMINI_PRIMARY_API_KEY`, `GEMINI_SECONDARY_API_KEY`, `GOOGLE_API_KEY` | 52 each | text, video, image, music, TTS, embeddings |
| Groq | `GROQ_API_KEY` | 15 | fastest tokens/sec; Whisper transcription |
| GLM (Zhipu) | `GLM_API_KEY` | 9 | glm-4.5 → glm-5.3 |
| Cerebras | `CEREBRAS_API_KEY` | 3 | lowest latency anywhere |
| Mercury | `MERCURY_API_KEY` | 1 | `mercury-2`, a diffusion LLM |
| HuggingFace | `HF_TOKEN` | hub | weights, datasets, Spaces, ZeroGPU |
| Black Forest Labs | `BFL_API_KEY` | — | FLUX image generation |
| Claude Code | `CLAUDE_CODE_OAUTH_TOKEN` | — | agent work, not a models API |

The three Gemini rows are **one catalogue behind three keys** — three independent
quotas, not three catalogues.

## Two things that are not API keys

**Antigravity (`agy`) is the Gemini Pro subscription path**, and it is a CLI, not an
HTTP API. Two Pro accounts. It carries heavy process overhead — measured 46.3s for a
trivial prompt on 2026-08-18, up from the earlier 18–27s band — and can return an
empty response with exit 0. So: never behind a route a UI waits on, never a timeout
under 90s, assert non-empty, retry once. Batch and background only.

The roster is bigger than Gemini (`agy models`, verified 2026-08-18): Flash
3.5/3.6/3.7 at three thinking levels, `gemini-3.1-pro-{high,low}`,
**`claude-opus-4-6-thinking`**, `claude-sonnet-4-6`, and `gpt-oss-120b-medium`.
The Claude credits make agy a second frontier pool: use `claude-opus-4-6-thinking`
for background second opinions and heavy offline analysis, or as overflow when the
`claude` CLI subscription runs tight. The 46s overhead applies to every model on
the roster — model choice changes quality, not latency.

**Bedrock** lives in the `vibelaunch-worker` Doppler project
(`AWS_BEARER_TOKEN_BEDROCK`, `CLAUDE_CODE_USE_BEDROCK`), not here. It is paid, and
covered by the AWS Activate credits — see `AWS.md`.

## Gemini media models — measured serving state (probed 2026-08-18, $0 spent)

The fleet audit's "video/image/music already in the fleet" needs this
correction: **catalogued ≠ servable.** Live probes against all three keys:

- **Serve today, free tier**: gemini-embedding-001/-2 (~1s),
  gemini-2.5-flash-preview-tts (12.3s/sentence),
  gemini-3.1-flash-tts-preview (6.0s/sentence).
- **Billing-gated, not broken**: lyria-3 (music), gemini-omni-flash-preview,
  nano-banana-pro / gemini-3-pro-image — 429 `limit:0` free-tier on every
  key and both GCP projects. Paid-only models; our account has no billing
  enabled. Unlocking is a billing-account change, not integration work.
- **DEAD**: Imagen 4, all three tiers — retired 2026-08-17, measured 404 the
  day after; Google's error names the replacement: `gemini-3.1-flash-image`.
  /models still lists the corpses — the catalogue lies.
- **Veo 3.1: not probed** — no free tier ($0.05–0.60/s by tier), async
  billing, 5s minimum unconfirmed. Needs a deliberate human-approved
  single-clip test, never an unattended one.

Raw log + scripts: session scratchpad `media-probe/` (2026-08-18).

## Speech: TTS live, diarization funded

**ElevenLabs** — `ELEVENLABS_API_KEY`, in Doppler since 2026-08-18 (moved from
`.zshrc`; verified live, /v1/user 200). The studio bridge's media-provider
registry picks it up: `capabilities: tts`. Rotation recommended at leisure — a
truncated fragment of the key landed in one local agent transcript during the
move.

**Deepgram** — `DEEPGRAM_API_KEY` in Doppler since 2026-08-18 (verified live,
/v1/projects 200). $200 credits on the account. nova-3 `diarize=true` is the
diarization provider for the podcast pack: per-word speaker labels. This
closed the fleet's one diarization gap.

## Picking one

- **A route the UI waits on** → Cerebras or Groq. 1–3s, free tier. Fast enough that
  `job_id` + poll plumbing is unnecessary.
- **Structured JSON output** → Gemini Flash or GLM. Small models fail at nested schemas.
- **Transcription** → Groq, `whisper-large-v3-turbo`.
- **Bulk / offline** → OpenRouter free tier, or `agy`.
- **Never** → loading a local model through `transformers` on MPS. `src/enhance_prompt.py`
  does this with Qwen2.5-1.5B and reloads on every call; it predates the fleet and
  nothing should copy it.

## Notable model IDs

```
gemini   gemini-3.7-flash · gemini-3.5-flash · gemini-2.5-pro · gemini-flash-latest
video    veo-3.1-generate-preview · veo-3.1-fast-generate-preview · veo-3.1-lite-generate-preview
image    imagen-4.0-{fast,ultra}-generate-001 · gemini-3-pro-image · nano-banana-pro-preview
audio    lyria-3-pro-preview · gemini-2.5-flash-preview-tts · gemini-omni-flash-preview
groq     openai/gpt-oss-120b · llama-3.3-70b-versatile · qwen/qwen3.6-27b · whisper-large-v3-turbo
cerebras gpt-oss-120b · gemma-4-31b · zai-glm-4.7
glm      glm-5.3 · glm-5.2 · glm-5-turbo · glm-4.5-air
free     nvidia/nemotron-3-ultra-550b-a55b:free · openai/gpt-oss-20b:free · google/gemma-4-31b-it:free
```

**Veo, Imagen and Lyria are billed, with no free API tier.** Veo 3.1 is $0.40/s
(720p/1080p), Fast $0.15/s, Lite from $0.03/s. A 5-second Lite clip is $0.15. Google
Flow gives free daily credits but is a consumer web UI — it cannot be scripted, and
its output carries a **Veo watermark**.

## Gotcha: Cloudflare blocks Python clients

Cerebras and Groq return **HTTP 403, `error code: 1010`** to `urllib` — that is
Cloudflare's bot-signature block, not an auth failure. Both return 200 immediately
under `curl`. A key-presence check calls them live for the wrong reason; a naive
liveness check calls them dead. Use curl, or set a browser-like User-Agent.

## Re-verify

```bash
doppler run -p unfoundbox -c dev_personal -- bash -c \
  'curl -sS -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models | head -c 300'
```

Endpoints: `api.cerebras.ai/v1/models` · `api.groq.com/openai/v1/models` ·
`openrouter.ai/api/v1/models` · `integrate.api.nvidia.com/v1/models` ·
`api.inceptionlabs.ai/v1/models` · `open.bigmodel.cn/api/paas/v4/models` ·
`generativelanguage.googleapis.com/v1beta/models` (header `x-goog-api-key`).

Never print secret values. Names, lengths and model IDs only.
