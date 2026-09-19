# SpacePilot voice bridge (browser prototype)

A cheap, cloud duplex-voice prototype: `voice.html` is a browser page that
opens a full-duplex WebSocket to `voice-bridge.py`, which proxies to Gemini
Live and injects your Doppler API key server-side so the browser never sees
it. One tool is wired up — `diagnose_hardware_fans`, which reports real CPU
and memory numbers pulled from `psutil` on this machine, not invented ones.

**This is the cloud prototype, not the product.** The Swift app
(`native/SpaceBar`, see `docs/LOCAL-TEST.md`) is the local path — on-device
speech recognition, on-device Apple Intelligence when it is on, and no
round trip to Google. This bridge exists for testing the duplex-voice idea
quickly, and it depends on Gemini being reachable and paid for.

## What it needs

`GEMINI_PRIMARY_API_KEY` (or `GEMINI_API_KEY` / `GOOGLE_API_KEY` as
fallbacks), passed via environment variables or a secrets manager.

## Running it

Two processes, both on `localhost:8090`:

```bash
# 1. The bridge — proxies to Gemini Live
GEMINI_API_KEY="your-key" python voice/web/voice-bridge.py
```

```bash
# 2. The page — open voice/web/voice.html in a browser (file:// is fine;
#    it connects out to ws://localhost:8090, so no HTTP server is required)
open voice/web/voice.html
```

The page auto-connects to the bridge on load and starts listening.
Interrupting mid-sentence (barge-in) clears the playback buffer immediately.
