#!/usr/bin/env python3
"""Video Engine Registry for Pluto.

Provides dynamic lookup, alias resolution, and graceful fallback
for video generation engines (LTX-Video 2.5, Wan2.1 1.3B/14B, HunyuanVideo).
"""

import logging
from typing import Dict, Any, List, Optional, Type, Union, Callable

from spacepilot.engines.base import BaseVideoEngine, EngineSpec
from spacepilot.engines.ltx_engine import LTXVideoEngine
from spacepilot.engines.wan_engine import WanVideoEngine
from spacepilot.engines.hunyuan_engine import HunyuanVideoEngine

logger = logging.getLogger("pluto.engines")

DEFAULT_ENGINE_ID = "ltx-2.5"

# Factory mappings
ENGINE_FACTORIES: Dict[str, Callable[..., BaseVideoEngine]] = {
    "ltx-2.5": lambda **kw: LTXVideoEngine(**kw),
    "wan-2.1-1.3b": lambda **kw: WanVideoEngine(model_size="1.3B", **kw),
    "wan-2.1-14b": lambda **kw: WanVideoEngine(model_size="14B", **kw),
    "hunyuan-video": lambda **kw: HunyuanVideoEngine(**kw),
}

# Aliases mapped to canonical engine IDs
ENGINE_ALIASES: Dict[str, str] = {
    "ltx": "ltx-2.5",
    "ltx25": "ltx-2.5",
    "ltx-video": "ltx-2.5",
    "ltx-video-2.5": "ltx-2.5",
    "ltx-2.5-nf4": "ltx-2.5",
    "ltx-2.5-fp8": "ltx-2.5",
    "wan": "wan-2.1-14b",
    "wan2.1": "wan-2.1-14b",
    "wan-14b": "wan-2.1-14b",
    "wan2.1-14b": "wan-2.1-14b",
    "wan-video": "wan-2.1-14b",
    "wan-1.3b": "wan-2.1-1.3b",
    "wan2.1-1.3b": "wan-2.1-1.3b",
    "hunyuan": "hunyuan-video",
    "hunyuanvideo": "hunyuan-video",
    "hunyuan-video-dit": "hunyuan-video",
}


def normalize_engine_id(engine_id: Optional[str]) -> str:
    """Normalize engine identifier string."""
    if not engine_id:
        return DEFAULT_ENGINE_ID
    cleaned = engine_id.strip().lower().replace("_", "-")
    return ENGINE_ALIASES.get(cleaned, cleaned)


def register_engine(engine_id: str, factory_or_cls: Union[Type[BaseVideoEngine], Callable[..., BaseVideoEngine]]) -> None:
    """Register a new video engine or custom adapter."""
    canon_id = engine_id.strip().lower().replace("_", "-")
    if isinstance(factory_or_cls, type) and issubclass(factory_or_cls, BaseVideoEngine):
        ENGINE_FACTORIES[canon_id] = lambda **kw: factory_or_cls(**kw)
    elif callable(factory_or_cls):
        ENGINE_FACTORIES[canon_id] = factory_or_cls
    else:
        raise ValueError(f"Invalid engine factory or class: {factory_or_cls}")


def get_video_engine(engine_id: Optional[str] = DEFAULT_ENGINE_ID, **kwargs) -> BaseVideoEngine:
    """Retrieve an initialized video engine adapter with fallback to default engine.

    Args:
        engine_id: Identifier or alias for the desired engine.
        **kwargs: Optional configuration passed to the engine constructor.

    Returns:
        BaseVideoEngine instance.
    """
    canonical_id = normalize_engine_id(engine_id)

    factory = ENGINE_FACTORIES.get(canonical_id)
    if factory is not None:
        return factory(**kwargs)

    # Fallback to default engine
    logger.warning(
        f"Unknown video engine '{engine_id}' (resolved to '{canonical_id}'). "
        f"Falling back to default engine '{DEFAULT_ENGINE_ID}'."
    )
    default_factory = ENGINE_FACTORIES[DEFAULT_ENGINE_ID]
    return default_factory(**kwargs)


def list_video_engines() -> List[EngineSpec]:
    """List all supported video engines and their specifications."""
    specs = []
    for eng_id, factory in ENGINE_FACTORIES.items():
        try:
            engine_inst = factory()
            specs.append(engine_inst.get_spec())
        except Exception as e:
            logger.error(f"Failed to instantiate spec for engine '{eng_id}': {e}")
    return specs
