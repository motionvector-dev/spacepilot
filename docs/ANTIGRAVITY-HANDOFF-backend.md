# Antigravity task — pluto video-API backend: add /clips/generate, verify contracts

> **Status:** Open spec — unstarted. Read this as a task to do, not a status report.
> **Verified:** 2026-08-22, by grepping `src/` for a `/clips/generate` route. None exists.
> **Supersedes / Superseded by:** none

You built this pluto backend (Python, `server.py` serves `/health`, `/enhance`, `/generate` at localhost:8001) and the frontend VideoGen UI. Now close the backend gaps the frontend depends on. The repo now has a git baseline commit — commit your work as you go so there's an undo trail.

## Task 1 (primary): implement `POST /clips/generate`
The frontend `/Users/saurabh/code/katana/upscaler/upscaler-frontend/src/views/AutoClip.vue` does local Whisper transcription in the browser, then POSTs to `${VITE_VIDEO_API_URL}/clips/generate`. This endpoint does NOT exist in `server.py` yet — add it.
- **Read `AutoClip.vue` first** to confirm the EXACT request body it sends (the transcript shape) and the EXACT response shape it expects (clips array — fields like start/end/title/score/text). The frontend contract is the source of truth; match it precisely.
- **Detection logic:** reuse the transcript-based clip-detection approach from `/Users/saurabh/code/katana/katana.video` (it scores a Whisper transcript with an LLM / the Modal `intro-clips-v2` endpoint to find engaging segments — see `backend/src/modules/clips.js` and `ml-worker*/src/algorithms/qna.py`). You may either call the existing Modal clips endpoint (`MODAL_CLIPS_ENDPOINT`, transcript-only input — no media file needed) or reimplement with a direct LLM call. Transcript in → ranked clip time-spans out. Do NOT require the media file server-side; the browser already has it and cuts clips locally.
- Keep it consistent with how `/enhance` and `/generate` are structured (same FastAPI app, same error/response conventions).

## Task 2: verify `/generate` and `/enhance` match the frontend
Read `spacepilot/views/VideoGen.vue` and `spacepilot/views/VideoGenV2.vue` in the frontend repo. Confirm the request bodies they send to `/generate` and `/enhance` (prompt, resolution, frames, mode, autoEnhance…) and the response shapes they expect line up with what `server.py` implements. Fix any drift on the backend side (do NOT change the frontend). Note anything the frontend sends that the backend ignores.

## Constraints
- Keep `server.py` runnable (it should still start and serve /health). If it needs new deps, update requirements and note them.
- Do NOT touch the frontend repo — it's read-only reference here for the contract. Another agent (Codex) and Claude are working in it.
- Commit your changes with clear messages. Report: the exact `/clips/generate` request+response contract you implemented, any contract drift you found/fixed on /generate & /enhance, and how to run/test the server.
