"""Pluto Multi-Model DiT Video Engines.

Polymorphic adapters for LTX-Video 2.5, Wan2.1 1.3B/14B, and HunyuanVideo.
"""

from src.engines.base import BaseVideoEngine, EngineSpec
from src.engines.ltx_engine import LTXVideoEngine
from src.engines.wan_engine import WanVideoEngine
from src.engines.hunyuan_engine import HunyuanVideoEngine
from src.engines.registry import (
    get_video_engine,
    list_video_engines,
    register_engine,
    normalize_engine_id,
    DEFAULT_ENGINE_ID,
)

__all__ = [
    "BaseVideoEngine",
    "EngineSpec",
    "LTXVideoEngine",
    "WanVideoEngine",
    "HunyuanVideoEngine",
    "get_video_engine",
    "list_video_engines",
    "register_engine",
    "normalize_engine_id",
    "DEFAULT_ENGINE_ID",
]
