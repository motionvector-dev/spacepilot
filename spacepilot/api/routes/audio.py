"""Audio generation and mixing routes."""

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, HTTPException, BackgroundTasks, UploadFile

from spacepilot.core.config import get_settings
from spacepilot.core.utils import run_ffmpeg, discard_partial, ffmpeg_error, write_meta
from spacepilot.api.deps import require_token, update_activity
from spacepilot.drivers.kokoro_driver import KokoroDriver
from spacepilot.services.audio import (
    CLOUD_NOT_READY,
    mlx_generate_audio,
    loudnorm_two_pass,
    peak_normalize,
    synthesize_voice,
)

router = APIRouter(tags=["audio"])


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
        from spacepilot.local_workers import local_worker_manager
        driver_res = local_worker_manager.dispatch(
            "voiceover",
            text=text,
            voice=req.voice,
            speed=req.speed,
            out_path=out_wav,
            target_lufs=req.target_lufs,
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


def transcribe_audio_file(input_path: Path, job_id: Optional[str] = None) -> Dict[str, Any]:
    """Decode any ffmpeg-readable audio file to 16kHz mono WAV, transcribe it
    with the local whisper.cpp driver, and report the real per-call wall time.

    Takes a path already on disk, not bytes — both callers (the HTTP route,
    which saves an upload first; the MCP tool, which gets a path because MCP
    client and server share a filesystem) have one to hand. Whisper.cpp does
    not do real incremental streaming partials, so this returns the complete
    transcript only; there is no partial-results mode here.
    """
    settings = get_settings()
    job_id = job_id or f"stt_{uuid.uuid4().hex[:10]}"
    wav_path = settings.outputs_dir / f"{job_id}.wav"
    txt_path = settings.outputs_dir / f"{job_id}.txt"

    start = time.perf_counter()
    conv = run_ffmpeg(["-i", str(input_path), "-ar", "16000", "-ac", "1", str(wav_path)])
    if conv.returncode != 0:
        discard_partial(wav_path)
        raise RuntimeError(f"could not decode uploaded audio: {ffmpeg_error(conv)}")

    from spacepilot.local_workers import local_worker_manager
    try:
        driver_res = local_worker_manager.dispatch(
            "transcription", audio_path=str(wav_path), out_path=str(txt_path),
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

    from spacepilot.local_workers import local_worker_manager
    start = time.perf_counter()
    driver_res = local_worker_manager.dispatch(
        "voiceover", text=text, voice=kokoro_voice, speed=speed,
        out_path=out_wav, target_lufs=target_lufs,
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
    }


@router.post("/api/speech/transcribe")
async def transcribe_speech_api(audio: UploadFile = File(...), _: None = Depends(require_token)):
    update_activity()
    settings = get_settings()
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="audio file is empty")

    job_id = f"stt_{uuid.uuid4().hex[:10]}"
    suffix = Path(audio.filename or "").suffix or ".webm"
    src_path = settings.outputs_dir / f"{job_id}_in{suffix}"
    src_path.write_bytes(raw)
    try:
        return transcribe_audio_file(src_path, job_id=job_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"transcription failed: {str(e)}")
    finally:
        discard_partial(src_path)


class SpeechSayRequest(BaseModel):
    text: str = Field(max_length=8000)
    voice_id: str = Field("shannon", pattern=r"^[A-Za-z0-9_+.-]{1,64}$")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    target_lufs: float = Field(-16.0, ge=-30.0, le=-6.0)


@router.post("/api/speech/say")
def speech_say_api(req: SpeechSayRequest, _: None = Depends(require_token)):
    update_activity()
    try:
        return say_text(req.text, req.voice_id, req.speed, req.target_lufs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"speech synthesis failed: {str(e)}")
