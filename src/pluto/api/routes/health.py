"""Health, status, token, and live reload routes."""

import time
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.pluto.core.config import get_settings
from src.pluto.services.gpu_lifecycle import get_cached_status

router = APIRouter()


@router.get("/healthz")
async def healthz():
    """Dependency-free process liveness for local supervisors."""
    return {"status": "ok"}


@router.get("/api/token")
def get_token():
    """Hand the UI its session token."""
    settings = get_settings()
    return {"token": settings.studio_token}


@router.get("/api/status")
def get_status():
    """Retrieve bounded, single-flight status of the GPU box and worker."""
    return get_cached_status()


@router.get("/api/live-reload")
async def live_reload_sse():
    """Server-Sent Events stream for development hot-reloading."""
    async def event_generator():
        while True:
            await asyncio.sleep(5)
            yield f"data: ping\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
