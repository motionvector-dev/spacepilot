"""The local-status answer, built once and served to every surface.

`spacepilot_get_local_status` (MCP) and `GET /api/compute/local-status` (HTTP)
each built this payload themselves. At one instant on one machine the MCP tool
reported `loaded_models: ["kokoro-82m-tts", "span-4k-upscaler"]` while the HTTP
route reported `loaded_models: []` — same field, same moment, two answers — and
neither model was loaded: the two names were 75-byte marker files left by the
gated mock downloader, at the same time as `doctor` correctly said the Kokoro
weights were not found.

So this module is the one implementation, and it renames the claim as well as
fixing the divergence. Nothing is ever loaded into either of these processes,
so `loaded_models` is empty and stays empty; what the cache holds is reported
as what it is, cached weights or a stub marker.
"""

from typing import Any, Dict

LOADED_MODELS_NOTE = (
    "deprecated and always empty: neither surface loads weights into its own "
    "process, and this field used to list cache entries — including stub "
    "markers that were not weights at all. Read cached_weight_model_ids."
)


def local_status_payload() -> Dict[str, Any]:
    """Live local inference status: one dict, identical on every surface."""
    from spacepilot.device_probe import probe_local_device, usable_memory_report
    from spacepilot.model_recommender import cached_model_report

    profile = probe_local_device()
    memory = usable_memory_report(profile)
    cache = cached_model_report()
    return {
        "status": "online",
        "backend": profile.backend,
        "device_name": profile.device_name,
        "vram_usable_gb": memory["usable_memory_gib"],
        "vram_usable_known": memory["usable_memory_known"],
        "memory_limit_source": memory["memory_limit_source"],
        "cached_weight_model_ids": cache["cached_weight_model_ids"],
        "stub_marker_ids": cache["stub_marker_ids"],
        "loaded_models": [],
        "loaded_models_note": LOADED_MODELS_NOTE,
        "is_local_capable": profile.is_local_capable,
    }
