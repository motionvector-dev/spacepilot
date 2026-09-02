#!/usr/bin/env python3
"""Multimodal model recommender engine for SpacePilot."""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from spacepilot.device_probe import GIB, DeviceProfile, probe_local_device, usable_memory_bytes
from spacepilot.paths import model_recommender_cache_dir, model_recommender_cache_read_dirs
from spacepilot.verdict import RUNS_SLOWLY, RUNS_WELL, UNKNOWN, WONT_FIT, UnknownModel, fit_verdict

# Direct-import compatibility. The value is now canonical and all fallback
# reads go through paths.py rather than embedding a second directory policy.
MODELS_CACHE = model_recommender_cache_dir()


@dataclass
class ModelEntry:
    model_id: str
    name: str
    task: str  # "voiceover", "storyboard", "video_draft", "video_pro", "super_resolution"
    precision: str  # "fp16", "q4_k_m", "nf4", "fp8"
    size_gb: float
    min_vram_gb: float
    recommended_vram_gb: float
    download_url: str
    sha256: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


RECOMMENDED_MODEL_CATALOG: List[ModelEntry] = [
    ModelEntry(
        model_id="kokoro-82m-tts",
        name="Kokoro 82M TTS",
        task="voiceover",
        precision="fp16",
        size_gb=0.32,
        min_vram_gb=0.5,
        recommended_vram_gb=1.0,
        download_url="https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v0_19.onnx",
        sha256="mock_sha256_kokoro_82m_v019",
        description="Ultra-fast high quality TTS synthesis with EBU R128 sidechain ducking support."
    ),
    ModelEntry(
        model_id="qwen2.5-3b-instruct-gguf",
        name="Qwen 2.5 3B Instruct",
        task="storyboard",
        precision="q4_k_m",
        size_gb=2.1,
        min_vram_gb=3.5,
        recommended_vram_gb=6.0,
        download_url="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        sha256="mock_sha256_qwen25_3b_q4km",
        description="Fast narrative script decomposition and prompt enhancement for edge devices."
    ),
    ModelEntry(
        model_id="deepseek-r1-distill-qwen-7b-gguf",
        name="DeepSeek R1 Distill Qwen 7B",
        task="storyboard",
        precision="q4_k_m",
        size_gb=4.8,
        min_vram_gb=7.0,
        recommended_vram_gb=12.0,
        download_url="https://huggingface.co/unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        sha256="mock_sha256_deepseek_r1_7b_q4km",
        description="Reasoning-focused screenplay deconstruction with locked character seeds & camera vectors."
    ),
    ModelEntry(
        model_id="ltx-video-2.5-nf4",
        name="LTX-Video 2.5 NF4 Draft",
        task="video_draft",
        precision="nf4",
        size_gb=11.2,
        min_vram_gb=14.0,
        recommended_vram_gb=20.0,
        download_url="https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2.5-nf4.safetensors",
        sha256="mock_sha256_ltx_video_25_nf4",
        description="Local single-take video diffusion plate generator at 512x288 / 768x432."
    ),
    ModelEntry(
        model_id="ltx-video-2.5-fp8",
        name="LTX-Video 2.5 FP8 Cinema",
        task="video_pro",
        precision="fp8",
        size_gb=22.4,
        min_vram_gb=24.0,
        recommended_vram_gb=32.0,
        download_url="https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2.5-fp8.safetensors",
        sha256="mock_sha256_ltx_video_25_fp8",
        description="Full fidelity 24fps high dynamic range cinematic video diffusion model."
    ),
    ModelEntry(
        model_id="span-4k-upscaler",
        name="SPAN 4K Super-Resolution",
        task="super_resolution",
        precision="fp16",
        size_gb=0.064,
        min_vram_gb=0.8,
        recommended_vram_gb=2.0,
        download_url="https://huggingface.co/motionvector/SPAN-4K/resolve/main/span_4k.pt",
        sha256="mock_sha256_span_4k_v1",
        description="Spatial-temporal super-resolution neural upscaler for crisp 4K master plates."
    ),
]


def is_model_downloaded(model_id: str) -> bool:
    """Check if a model exists in the local cache."""
    return any(
        (root / model_id).is_file() and (root / model_id).stat().st_size > 10
        for root in model_recommender_cache_read_dirs()
    )


def downloaded_model_ids() -> List[str]:
    """Canonical and legacy cached model ids, deduplicated in precedence order."""
    values: List[str] = []
    for root in model_recommender_cache_read_dirs():
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.name not in values:
                values.append(path.name)
    return values


def _entry_verdict(entry: ModelEntry, profile: DeviceProfile,
                   usable_bytes: Optional[int], usable_vram: float) -> Dict[str, Any]:
    """The shared verdict words, for a catalogue entry.

    A registry variant is graded by `fit_verdict` — the same call `/v1/models`
    and `spacepilot models` make, so all three read identically. This
    catalogue predates the registry and most of its entries are not variants;
    those are graded here by the same arithmetic, into the same three words,
    rather than into a fourth private vocabulary ("Optimal Local Execution").
    """
    try:
        return fit_verdict(entry.model_id, profile)
    except UnknownModel:
        pass
    if usable_bytes is None:
        return {"level": UNKNOWN,
                "reason": "this machine's accelerator memory has not been read",
                "headroom_bytes": None}
    headroom = int(usable_bytes - entry.recommended_vram_gb * GIB)
    if usable_vram >= entry.recommended_vram_gb:
        level, reason = RUNS_WELL, f"{usable_vram:.1f} GB available, {entry.recommended_vram_gb:.1f} GB recommended"
    elif usable_vram >= entry.min_vram_gb:
        level, reason = RUNS_SLOWLY, f"{usable_vram:.1f} GB available, below the {entry.recommended_vram_gb:.1f} GB recommended"
    else:
        level, reason = WONT_FIT, f"{usable_vram:.1f} GB available, {entry.min_vram_gb:.1f} GB is the minimum"
    return {"level": level, "reason": reason, "headroom_bytes": headroom}


def recommend_models_for_device(profile: Optional[DeviceProfile] = None) -> Dict[str, Any]:
    """Evaluate device capability and produce task-based recommendations."""
    if profile is None:
        profile = probe_local_device()

    usable_bytes = usable_memory_bytes(profile)
    usable_vram = 0.0 if usable_bytes is None else usable_bytes / GIB
    recommendations = []

    for entry in RECOMMENDED_MODEL_CATALOG:
        is_downloaded = is_model_downloaded(entry.model_id)

        if usable_bytes is None:
            # Nobody measured this machine's accelerator memory. Routing every
            # model to cloud on the strength of that is a recommendation built
            # on a number we do not have.
            fit_score = None
            route = "unknown"
            fit_label = "Not enough is known about this machine"
        elif usable_vram >= entry.recommended_vram_gb:
            fit_score = 1.0
            route = "local"
            fit_label = "Optimal Local Execution"
        elif usable_vram >= entry.min_vram_gb:
            fit_score = 0.8
            route = "local_constrained"
            fit_label = "Supported (Tight Headroom)"
        else:
            fit_score = max(0.1, round(usable_vram / entry.min_vram_gb, 2))
            route = "cloud_spot"
            fit_label = "Cloud Spot Recommended"

        recommendations.append({
            "model_id": entry.model_id,
            "name": entry.name,
            "task": entry.task,
            "precision": entry.precision,
            "size_gb": entry.size_gb,
            "min_vram_gb": entry.min_vram_gb,
            "recommended_vram_gb": entry.recommended_vram_gb,
            "fit_score": fit_score,
            "execution_route": route,
            "fit_label": fit_label,
            "verdict": _entry_verdict(entry, profile, usable_bytes, usable_vram),
            "is_downloaded": is_downloaded,
            "download_url": entry.download_url,
            "description": entry.description,
        })

    return {
        "device": profile.to_dict(),
        "recommendations": recommendations,
        "total_models": len(recommendations),
        "cache_dir": str(MODELS_CACHE),
    }


def download_model_mock(model_id: str) -> Dict[str, Any]:
    """Mock/Staging model downloader creating cache payload."""
    # GATED 2026-08-24: this wrote a stub text file with a fake sha256 and
    # returned {"status": "downloaded"} — a fabricated download. Disabled so it
    # can no longer report fake success. The real path is a huggingface_hub
    # wrapper writing to the HF cache (see docs/THESIS.md). Mock body below dead.
    raise NotImplementedError(
        "Model download is not implemented; this wrote a stub with a mock "
        "sha256 and claimed success. Gated 2026-08-24."
    )
    target_entry = next((m for m in RECOMMENDED_MODEL_CATALOG if m.model_id == model_id), None)
    if not target_entry:
        return {"success": False, "error": f"Model {model_id} not found in catalogue."}

    MODELS_CACHE.mkdir(parents=True, exist_ok=True)
    target_file = MODELS_CACHE / model_id
    
    with open(target_file, "w") as f:
        f.write(f"model_id: {model_id}\nsize_gb: {target_entry.size_gb}\nsha256: {target_entry.sha256}\n")

    return {
        "success": True,
        "model_id": model_id,
        "path": str(target_file),
        "size_gb": target_entry.size_gb,
        "status": "downloaded"
    }
