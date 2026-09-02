"""Health, status, token, and live reload routes."""

import time
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from spacepilot.core.config import get_settings
from spacepilot.services.gpu_lifecycle import get_cached_status

router = APIRouter()


@router.get("/healthz")
async def healthz():
    """Dependency-free process liveness for local supervisors."""
    return {"status": "ok"}


@router.get("/api/token")
def get_token(request: Request):
    """Hand the UI its session token.

    Loopback callers only. This is the key to every other gate on the server,
    including the shell websocket, so it stays unreachable even if someone
    widens the bind later or a proxy is put in front.
    """
    from spacepilot.api.security import is_loopback_client

    client = request.client.host if request.client else None
    if not is_loopback_client(client):
        raise HTTPException(
            status_code=403,
            detail="The session token is issued to this machine only.",
        )
    return {"token": get_settings().studio_token}


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
