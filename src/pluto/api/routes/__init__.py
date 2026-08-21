"""SpacePilot API Routes."""

from .audio import router as audio_router
from .health import router as health_router
from .compute import router as compute_router
from .engines import router as engines_router
from .storyboard import router as storyboard_router
from .views import router as views_router
from .assets import router as assets_router
from .gpu import router as gpu_router
from .generate import router as generate_router
from .lora import router as lora_router

__all__ = [
    "audio_router",
    "health_router",
    "compute_router",
    "engines_router",
    "storyboard_router",
    "views_router",
    "assets_router",
    "gpu_router",
    "generate_router",
    "lora_router",
]
