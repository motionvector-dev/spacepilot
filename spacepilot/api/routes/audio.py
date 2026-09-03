"""Audio generation and mixing routes."""

import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, Form, HTTPException, BackgroundTasks, UploadFile
from fastapi.responses import StreamingResponse

from spacepilot.core.config import get_settings
from spacepilot.core.utils import run_ffmpeg, discard_partial, ffmpeg_error, write_meta
from spacepilot.api.deps import require_token, require_speech_token, update_activity
from spacepilot.drivers.kokoro_driver import KokoroDriver
from spacepilot.local_workers import local_worker_manager
from spacepilot.services.audio import (
    CLOUD_NOT_READY,
    mlx_generate_audio,
    loudnorm_two_pass,
    peak_normalize,
    synthesize_voice,
)

router = APIRouter(tags=["audio"])
logger = logging.getLogger("spacepilot.api.audio")

MAX_TRANSCRIBE_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB: generous for speech, not for abuse

# A denylist, not an allowlist: real clients disagree on what audio gets
# tagged as ("audio/webm", "audio/wav", but also plain "application/
# octet-stream" from curl and plenty of generic multipart libraries, and
# some encoders even tag audio-only webm as "video/webm"). ffmpeg will
# reject genuinely unreadable content on its own; this only screens out
# the unambiguous non-audio cases.
REJECTED_TRANSCRIBE_CONTENT_TYPES = ("text/", "image/", "application/json", "application/pdf")

# Every subprocess-backed driver call below passes this so a hung whisper-cli
# or kokoro_runner.py can't block a worker thread forever. Generous relative
# to real measured latencies (well under 1s on this machine) without being
# so tight that a slower box's legitimate call gets killed mid-synthesis.
SUBPROCESS_TIMEOUT_SEC = 120.0


class MusicRequest(BaseModel):
    prompt: str = Field(max_length=4000)
    lyrics: str = Field(max_length=8000)
    duration_seconds: float = Field(30.0, ge=1, le=360, allow_inf_nan=False)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    backend: str = Field("local", pattern=r"^(local|cloud)$")


class VoiceRequest(BaseModel):
    text: str = Field(max_length=8000)
    voice: str = Field("af_heart", pattern=r"^[A-Za-z0-9_+.-]{1,64}$")
    speed: float = Field(1.0, ge=0.5, le=2.0, allow_inf_nan=False)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    backend: str = Field("local", pattern=r"^(local|mlx|cloud)$")


class MixDuckedAudioRequest(BaseModel):
    voice_job_id: str
    bgm_job_id: Optional[str] = None
    bgm_preset: Optional[str] = "ambient-cinematic"
    target_lufs: float = Field(default=-16.0, ge=-24.0, le=-10.0)
    video_job_id: Optional[str] = None


class LocalSynthesizeAudioRequest(BaseModel):
    text: str = Field(max_length=8000)
    voice: str = Field("af_heart", pattern=r"^[A-Za-z0-9_+.-]{1,64}$")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    target_lufs: float = Field(-16.0, ge=-30.0, le=-6.0)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)


def queued_audio_job(meta: dict) -> dict:
    settings = get_settings()
    write_meta(settings.outputs_dir / f"{meta['id']}.json", meta)
    return {"status": "queued", "job_id": meta["id"], "kind": meta["kind"], "meta": meta}


@router.post("/api/generate/music")
def generate_music_api(req: MusicRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
    settings = get_settings()
    if req.backend == "cloud":
        raise HTTPException(status_code=501, detail=CLOUD_NOT_READY)

    job_id = f"music_{uuid.uuid4().hex[:10]}"
    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647
    meta_file = settings.outputs_dir / f"{job_id}.json"
    raw_wav = settings.outputs_dir / f"{job_id}_raw.wav"
    out_wav = settings.outputs_dir / f"{job_id}.wav"
    meta = {
        "id": job_id,
        "kind": "music",
        "prompt": req.prompt,
        "lyrics": req.lyrics,
        "duration_seconds": req.duration_seconds,
        "seed": seed,
        "backend": req.backend,
        "status": "queued",
        "created_at": time.time(),
    }

    def _run_music():
        meta["status"] = "running"
        write_meta(meta_file, meta)
        start_t = time.time()
        try:
            api_mod = sys.modules.get("spacepilot.web_api")
            gen_fn = getattr(api_mod, "mlx_generate_audio", mlx_generate_audio) if api_mod else mlx_generate_audio
            audio = gen_fn(
                "/v1/audio/music-generations",
                {
                    "model": settings.music_model,
                    "prompt": req.prompt,
                    "lyrics": req.lyrics,
                    "duration_seconds": req.duration_seconds,
                    "seed": seed,
                },
                timeout=settings.ffmpeg_timeout_sec,
            )
            raw_wav.write_bytes(audio)
        except Exception as e:
            meta["status"] = "failed"
            meta["error"] = f"mlx-serve: {e}"
            discard_partial(raw_wav)
            write_meta(meta_file, meta)
            return

        meta["generate_sec"] = round(time.time() - start_t, 1)
        api_mod = sys.modules.get("spacepilot.web_api")
        ln_fn = getattr(api_mod, "loudnorm_two_pass", loudnorm_two_pass) if api_mod else loudnorm_two_pass
        norm = ln_fn(raw_wav, out_wav, settings.music_target_lufs)
        if norm.returncode != 0:
            meta["status"] = "failed"
            meta["error"] = ffmpeg_error(norm)
            meta["raw_path"] = str(raw_wav)
            discard_partial(out_wav)
            write_meta(meta_file, meta)
            return

        meta["status"] = "completed"
        meta["file_path"] = str(out_wav)
        meta["raw_path"] = str(raw_wav)
        meta["audio_url"] = f"/api/media/{job_id}.wav"
        meta["target_lufs"] = settings.music_target_lufs
        write_meta(meta_file, meta)

    background_tasks.add_task(_run_music)
    return queued_audio_job(meta)


@router.post("/api/generate/voice")
def generate_voice_api(req: VoiceRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
    settings = get_settings()
    if req.backend == "cloud":
        raise HTTPException(status_code=501, detail=CLOUD_NOT_READY)

    job_id = f"voice_{uuid.uuid4().hex[:10]}"
    meta_file = settings.outputs_dir / f"{job_id}.json"
    raw_wav = settings.outputs_dir / f"{job_id}_raw.wav"
    out_wav = settings.outputs_dir / f"{job_id}.wav"
    meta = {
        "id": job_id,
        "kind": "voice",
        "text": req.text,
        "voice": req.voice,
        "speed": req.speed,
        "seed": req.seed,
        "backend": req.backend,
        "status": "queued",
        "created_at": time.time(),
    }

    def _run_voice():
        meta["status"] = "running"
        write_meta(meta_file, meta)
        start_t = time.time()
        try:
            if req.backend == "mlx":
                payload = {
                    "model": settings.voice_model,
                    "input": req.text,
                    "voice": req.voice,
                    "speed": req.speed,
                    "response_format": "wav",
                }
                if req.seed is not None:
                    payload["seed"] = req.seed
                api_mod = sys.modules.get("spacepilot.web_api")
                gen_fn = getattr(api_mod, "mlx_generate_audio", mlx_generate_audio) if api_mod else mlx_generate_audio
                raw_wav.write_bytes(
                    gen_fn("/v1/audio/speech", payload, timeout=settings.ffmpeg_timeout_sec)
                )
            else:
                api_mod = sys.modules.get("spacepilot.web_api")
                syn_fn = getattr(api_mod, "synthesize_voice", synthesize_voice) if api_mod else synthesize_voice
                syn_fn(req.text, req.voice, req.speed, raw_wav)
        except Exception as e:
            meta["status"] = "failed"
            meta["error"] = f"{req.backend} backend: {e}"
            discard_partial(raw_wav)
            write_meta(meta_file, meta)
            return

        meta["generate_sec"] = round(time.time() - start_t, 1)
        api_mod = sys.modules.get("spacepilot.web_api")
        pn_fn = getattr(api_mod, "peak_normalize", peak_normalize) if api_mod else peak_normalize
        limit = pn_fn(raw_wav, out_wav, settings.voice_peak_dbfs)
        if limit.returncode != 0:
            meta["status"] = "failed"
            meta["error"] = ffmpeg_error(limit)
            discard_partial(out_wav)
            discard_partial(raw_wav)
            write_meta(meta_file, meta)
            return

        discard_partial(raw_wav)
        meta["status"] = "completed"
        meta["file_path"] = str(out_wav)
        meta["audio_url"] = f"/api/media/{job_id}.wav"
        meta["peak_dbfs"] = settings.voice_peak_dbfs
        write_meta(meta_file, meta)

    background_tasks.add_task(_run_voice)
    return queued_audio_job(meta)


@router.post("/api/audio/mix-ducked")
def mix_ducked_audio_api(req: MixDuckedAudioRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
    settings = get_settings()
    voice_id = req.voice_job_id.strip()
    voice_wav = settings.outputs_dir / f"{voice_id}.wav"
    if not voice_wav.exists():
        voice_wav = settings.outputs_dir / voice_id
        if not voice_wav.exists():
            raise HTTPException(status_code=404, detail=f"Voice track {req.voice_job_id} not found")

    job_id = f"ducked_{uuid.uuid4().hex[:10]}"
    meta_file = settings.outputs_dir / f"{job_id}.json"
    out_wav = settings.outputs_dir / f"{job_id}.wav"
    out_mp4 = settings.outputs_dir / f"{job_id}.mp4" if req.video_job_id else None

    bgm_wav = None
    if req.bgm_job_id:
        cand = settings.outputs_dir / f"{req.bgm_job_id}.wav"
        if not cand.exists():
            cand = settings.outputs_dir / req.bgm_job_id
        if cand.exists():
            bgm_wav = cand

    meta = {
        "id": job_id,
        "kind": "ducked_mix",
        "voice_job_id": req.voice_job_id,
        "bgm_job_id": req.bgm_job_id,
        "bgm_preset": req.bgm_preset,
        "target_lufs": req.target_lufs,
        "video_job_id": req.video_job_id,
        "status": "queued",
        "created_at": time.time(),
    }

    def _run_ducking():
        meta["status"] = "running"
        write_meta(meta_file, meta)
        nonlocal bgm_wav
        temp_bgm_created = False
        if not bgm_wav or not bgm_wav.exists():
            bgm_wav = settings.outputs_dir / f"{job_id}_bgm_bed.wav"
            temp_bgm_created = True
            tone_res = run_ffmpeg([
                "-f", "lavfi",
                "-i", "anoisesrc=d=60:c=pink:r=44100:a=0.08",
                "-af", "lowpass=f=400,volume=-12dB",
                "-t", "60",
                str(bgm_wav)
            ])
            if tone_res.returncode != 0:
                run_ffmpeg([
                    "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "60",
                    str(bgm_wav)
                ])

        filter_str = (
            f"[1:a]volume=0.85[bgm_in];"
            f"[bgm_in][0:a]sidechaincompress=threshold=0.08:ratio=4:attack=15:release=350[bgm_ducked];"
            f"[bgm_ducked][0:a]amix=inputs=2:duration=first:dropout_transition=2[mixed];"
            f"[mixed]loudnorm=I={req.target_lufs}:TP=-1.5:LRA=11[out]"
        )
        cmd = [
            "-i", str(voice_wav),
            "-i", str(bgm_wav),
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-c:a", "pcm_s16le",
            "-ar", "44100",
            str(out_wav)
        ]
        res = run_ffmpeg(cmd)
        if temp_bgm_created:
            discard_partial(bgm_wav)

        if res.returncode != 0:
            meta["status"] = "failed"
            meta["error"] = ffmpeg_error(res)
            discard_partial(out_wav)
            write_meta(meta_file, meta)
            return

        meta["status"] = "completed"
        meta["file_path"] = str(out_wav)
        meta["audio_url"] = f"/api/media/{job_id}.wav"
        meta["target_lufs"] = req.target_lufs

        if req.video_job_id and out_mp4:
            vid_path = settings.outputs_dir / f"{req.video_job_id}.mp4"
            if not vid_path.exists():
                vid_path = settings.outputs_dir / req.video_job_id
            if vid_path.exists():
                mux_res = run_ffmpeg([
                    "-i", str(vid_path),
                    "-i", str(out_wav),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    str(out_mp4)
                ])
                if mux_res.returncode == 0:
                    meta["muxed_video_url"] = f"/api/media/{job_id}.mp4"
                    meta["muxed_video_path"] = str(out_mp4)

        write_meta(meta_file, meta)

    background_tasks.add_task(_run_ducking)
    return queued_audio_job(meta)


@router.post("/api/audio/synthesize-local")
def synthesize_local_audio_api(req: LocalSynthesizeAudioRequest, _: None = Depends(require_token)):
    update_activity()
    settings = get_settings()
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    job_id = f"voice_local_{uuid.uuid4().hex[:10]}"
    out_wav = settings.outputs_dir / f"{job_id}.wav"
    meta_file = settings.outputs_dir / f"{job_id}.json"

    try:
        driver_res = local_worker_manager.dispatch(
            "voiceover",
            text=text,
            voice=req.voice,
            speed=req.speed,
            out_path=out_wav,
            target_lufs=req.target_lufs,
            timeout=SUBPROCESS_TIMEOUT_SEC,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local voice synthesis failed: {str(e)}")

    meta = {
        "id": job_id,
        "kind": "voice_local",
        "text": text,
        "voice": req.voice,
        "speed": req.speed,
        "target_lufs": req.target_lufs,
        "sample_rate": driver_res.get("sample_rate", 24000),
        "duration_sec": driver_res.get("duration_sec", 0.0),
        "status": "completed",
        "file_path": str(out_wav),
        "audio_url": f"/api/media/{job_id}.wav",
        "created_at": time.time(),
    }
    write_meta(meta_file, meta)
    return meta


# ─── Shared speech API (spike, 2026-09-03) ──────────────────────────────────
#
# Requested by a peer session building a browser air-drums demo on Chrome's
# on-device Gemini Nano, so their voice I/O doesn't duplicate what SpaceBar's
# own voice roadmap needs anyway. Both routes below are thin wrappers around
# functions that also back the MCP tools (mcp_server.py), so there is exactly
# one place that calls into whisper.cpp and exactly one that calls Kokoro.
#
# Two reserved logical voice ids, mapped to real Kokoro voices from the
# catalogue in kokoro_driver.py (VOICE_CATALOGUE) — not invented names.
SPEECH_VOICE_MAP: Dict[str, str] = {
    "shannon": "af_bella",  # bright_cinematic, female
    "archie": "am_puck",    # dynamic_energetic, male
}


TRANSCRIBE_MODEL_MAP: Dict[str, str] = {
    "whisper": "whisper-base-en",
    "whisper-base-en-q5-1": "whisper-base-en-q5-1",
}


def transcribe_audio_file(
    input_path: Path, job_id: Optional[str] = None, model: str = "whisper",
) -> Dict[str, Any]:
    """Decode any ffmpeg-readable audio file to 16kHz mono WAV, transcribe it
    with the local whisper.cpp driver, and report the real per-call wall time.

    Takes a path already on disk, not bytes — both callers (the HTTP route,
    which saves an upload first; the MCP tool, which gets a path because MCP
    client and server share a filesystem) have one to hand. Whisper.cpp does
    not do real incremental streaming partials, so this returns the complete
    transcript only; there is no partial-results mode here.

    `model` selects a whisper.cpp variant: "whisper" (default,
    whisper-base-en, f16) or "whisper-base-en-q5-1" (same model, quantized —
    smaller and faster, some accuracy tradeoff). Not Moonshine: no driver
    for it exists anywhere in this codebase yet, and moonshine.yaml's
    ctranslate2 weights need a preprocessing/inference recipe that has not
    been verified against the real upstream code — wiring it here would mean
    guessing at that recipe, which risks silently wrong transcripts. That is
    real driver work, out of scope for this spike.
    """
    variant_id = TRANSCRIBE_MODEL_MAP.get(model)
    if variant_id is None:
        raise ValueError(
            f"model '{model}' is not one of {sorted(TRANSCRIBE_MODEL_MAP)}"
        )

    settings = get_settings()
    job_id = job_id or f"stt_{uuid.uuid4().hex[:10]}"
    wav_path = settings.outputs_dir / f"{job_id}.wav"
    txt_path = settings.outputs_dir / f"{job_id}.txt"

    start = time.perf_counter()
    conv = run_ffmpeg(["-i", str(input_path), "-ar", "16000", "-ac", "1", str(wav_path)])
    if conv.returncode != 0:
        discard_partial(wav_path)
        raise RuntimeError(f"could not decode uploaded audio: {ffmpeg_error(conv)}")

    try:
        driver_res = local_worker_manager.dispatch(
            "transcription", audio_path=str(wav_path), out_path=str(txt_path),
            variant_id=variant_id, timeout=SUBPROCESS_TIMEOUT_SEC,
        )
        text = Path(driver_res["out_path"]).read_text().strip()
    finally:
        discard_partial(wav_path)
        discard_partial(txt_path)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    return {
        "status": "completed",
        "text": text,
        "latency_ms": latency_ms,
        "audio_seconds": driver_res.get("audio_seconds"),
        "weights": driver_res.get("weights"),
        "model_revision": driver_res.get("model_revision"),
        "model": model,
    }


def say_text(
    text: str,
    voice_id: str = "shannon",
    speed: float = 1.0,
    target_lufs: float = -16.0,
) -> Dict[str, Any]:
    """Synthesize speech with Kokoro for a reserved logical voice id
    ("shannon", "archie") or any raw Kokoro voice id, and report the real
    per-call wall time.

    Synchronous end to end: it returns only once the complete WAV exists on
    disk (the same architecture as /api/audio/synthesize-local). That is not
    a stand-in for streaming, so the timing field is named for what it
    actually measures rather than "first byte" or similar.

    `synthesis_ms` includes model load time on a cold call, same as it
    always has — `resident_session` and `load_seconds` (from
    KokoroDriver.infer(), see its docstring) surface that split honestly
    instead of leaving "warm vs cold" as something a caller has to
    infer from timing alone: `resident_session=True` and
    `load_seconds=None` means this call reused an already-loaded ONNX
    session; `load_seconds` being a real number means this call paid for
    loading it (in-process on a cold start, or an isolated subprocess
    entirely, per `resident_session`).
    """
    text = text.strip()
    if not text:
        raise ValueError("text cannot be empty")
    kokoro_voice = SPEECH_VOICE_MAP.get(voice_id, voice_id)
    if not KokoroDriver.is_valid_voice(kokoro_voice):
        raise ValueError(
            f"voice_id '{voice_id}' is neither a reserved id "
            f"({sorted(SPEECH_VOICE_MAP)}) nor a real Kokoro voice"
        )

    settings = get_settings()
    job_id = f"say_{uuid.uuid4().hex[:10]}"
    out_wav = settings.outputs_dir / f"{job_id}.wav"

    start = time.perf_counter()
    driver_res = local_worker_manager.dispatch(
        "voiceover", text=text, voice=kokoro_voice, speed=speed,
        out_path=out_wav, target_lufs=target_lufs, timeout=SUBPROCESS_TIMEOUT_SEC,
    )
    synthesis_ms = round((time.perf_counter() - start) * 1000, 1)

    return {
        "status": "completed",
        "voice_id": voice_id,
        "kokoro_voice": kokoro_voice,
        "audio_url": f"/api/media/{job_id}.wav",
        "sample_rate": driver_res.get("sample_rate", 24000),
        "duration_sec": driver_res.get("duration_sec", 0.0),
        "synthesis_ms": synthesis_ms,
        "load_seconds": driver_res.get("load_seconds"),
        "resident_session": driver_res.get("resident_session"),
    }


@router.get("/api/speech/voices")
def speech_voices_api():
    """What you can pass as voice_id to /api/speech/say: every real Kokoro
    voice id, plus the two reserved logical aliases layered on top. Read-only
    and unauthenticated on purpose — it spends no compute, and a consumer
    should not need to read this file's source to discover what's available.
    """
    return {
        "voices": KokoroDriver.get_voice_catalogue(),
        "aliases": dict(SPEECH_VOICE_MAP),
    }


@router.post("/api/speech/transcribe")
def transcribe_speech_api(
    audio: UploadFile = File(...),
    model: str = Form("whisper"),
    _: None = Depends(require_speech_token),
):
    """Plain `def`, not `async def`, on purpose.

    The body below is ffmpeg decode + a whisper-cli subprocess: ~0.6-0.8s of
    blocking work. An `async def` route runs directly on the event loop, so
    that blocked the whole daemon for every other request in flight for the
    duration of each transcribe call. A sync route gets dispatched to
    FastAPI's thread pool instead, which is what actually frees the loop.

    `model`: "whisper" (default) or "whisper-base-en-q5-1" (quantized,
    faster). See TRANSCRIBE_MODEL_MAP / transcribe_audio_file's docstring
    for why Moonshine isn't one of the options here.
    """
    update_activity()
    settings = get_settings()
    content_type = (audio.content_type or "").lower()
    if any(content_type.startswith(p) for p in REJECTED_TRANSCRIBE_CONTENT_TYPES):
        raise HTTPException(
            status_code=415, detail=f"unsupported content type: {content_type}")

    raw = audio.file.read(MAX_TRANSCRIBE_UPLOAD_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="audio file is empty")
    if len(raw) > MAX_TRANSCRIBE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"audio file exceeds the {MAX_TRANSCRIBE_UPLOAD_BYTES} byte limit",
        )

    job_id = f"stt_{uuid.uuid4().hex[:10]}"
    suffix = Path(audio.filename or "").suffix or ".webm"
    src_path = settings.outputs_dir / f"{job_id}_in{suffix}"
    src_path.write_bytes(raw)
    try:
        return transcribe_audio_file(src_path, job_id=job_id, model=model)
    except ValueError as e:
        # A bad `model` value only — short and safe to echo back as-is.
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # Covers the ffmpeg-decode failure and WhisperSubprocessError, both of
        # which can carry a full command line, weights path, or raw stderr —
        # fine for a local CLI, not for a response body this daemon's CORS
        # policy makes reachable from cross-origin demo pages. Full detail
        # goes to the server log, keyed by job_id for correlation.
        logger.error(f"[{job_id}] transcribe failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"transcription failed (ref {job_id}); see server log for detail",
        )
    except Exception as e:
        logger.error(f"[{job_id}] transcribe failed unexpectedly: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"transcription failed (ref {job_id}); see server log for detail",
        )
    finally:
        discard_partial(src_path)


class SpeechSayRequest(BaseModel):
    text: str = Field(max_length=8000)
    voice_id: str = Field("shannon", pattern=r"^[A-Za-z0-9_+.-]{1,64}$")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    target_lufs: float = Field(-16.0, ge=-30.0, le=-6.0)
    chunk: Optional[Literal["sentence"]] = Field(
        None,
        description=(
            "Set to 'sentence' to get an SSE stream of one synthesized part "
            "per sentence instead of a single JSON response. Sentence-level "
            "chunking only — not true low-level audio streaming."
        ),
    )


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_sentences(text: str) -> List[str]:
    """Split on sentence-ending punctuation followed by whitespace.

    Deliberately simple: good enough to chunk TTS into playable parts, not a
    linguistic sentence-boundary detector (abbreviations like "Dr." will
    split early — acceptable for this use).
    """
    text = text.strip()
    if not text:
        return []
    parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return parts or [text]


def _sse(payload: Dict[str, Any]) -> str:
    return "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"


def _stream_say_sentences(req: SpeechSayRequest) -> Generator[str, None, None]:
    """One `say_text` call per sentence, each part sent as it finishes.

    Sentence-level chunking, not true incremental audio streaming: the
    peer's contract only asked for the former. Emits one SSE event per
    completed part, then a final event carrying the full `parts` list (the
    shape a poll-style consumer would expect from one response), then a
    `[DONE]` sentinel matching the SSE convention already used by
    `/chat/completions` in `inference.py`.
    """
    sentences = split_into_sentences(req.text)
    if not sentences:
        yield _sse({"error": "text cannot be empty"})
        yield "data: [DONE]\n\n"
        return

    parts: List[Dict[str, Any]] = []
    for index, sentence in enumerate(sentences):
        try:
            result = say_text(sentence, req.voice_id, req.speed, req.target_lufs)
        except ValueError as e:
            yield _sse({"index": index, "sentence": sentence, "error": str(e)})
            continue
        except Exception as e:
            ref = uuid.uuid4().hex[:10]
            logger.error(f"[say-chunk:{ref}] sentence {index} failed: {e}")
            yield _sse({
                "index": index, "sentence": sentence,
                "error": f"speech synthesis failed (ref {ref}); see server log for detail",
            })
            continue

        part = {
            "audio_url": result["audio_url"],
            "duration_sec": result.get("duration_sec", 0.0),
        }
        parts.append(part)
        yield _sse({"index": index, "sentence": sentence, **part})

    yield _sse({"parts": parts})
    yield "data: [DONE]\n\n"


@router.post("/api/speech/say")
def speech_say_api(req: SpeechSayRequest, _: None = Depends(require_speech_token)):
    update_activity()
    if req.chunk == "sentence":
        return StreamingResponse(
            _stream_say_sentences(req), media_type="text/event-stream",
        )
    try:
        return say_text(req.text, req.voice_id, req.speed, req.target_lufs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # KokoroSubprocessError can carry a full command line and up to 3000
        # chars of raw stderr — not safe to echo to a response body this
        # daemon's CORS policy makes reachable from cross-origin demo pages.
        ref = uuid.uuid4().hex[:10]
        logger.error(f"[say:{ref}] speech synthesis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"speech synthesis failed (ref {ref}); see server log for detail",
        )
