"""SpacePilot Multi-Model DiT Video Engines.

Polymorphic adapters for LTX-Video 2.5, Wan2.1 1.3B/14B, and HunyuanVideo.
"""

from spacepilot.engines.base import BaseVideoEngine, EngineSpec
from spacepilot.engines.ltx_engine import LTXVideoEngine
from spacepilot.engines.wan_engine import WanVideoEngine
from spacepilot.engines.hunyuan_engine import HunyuanVideoEngine
from spacepilot.engines.registry import (
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
