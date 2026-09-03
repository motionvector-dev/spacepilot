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

    The IP check alone is not enough once `cors_origins` allows real remote
    pages (motionvector.dev, spacepilot.dev, the air-drums demo): a browser
    tab on any of those origins still connects from this machine's own
    loopback address when it calls a `127.0.0.1` URL, so `is_loopback_client`
    would pass for it too — CORSMiddleware is what would then decide whether
    that page's JS is allowed to read the response. Checking Origin here,
    independent of the general CORS allowlist, closes that: a page has to be
    genuinely local (no Origin header, or a loopback/.localhost one) to get
    the token at all, no matter what cors_origins otherwise permits for the
    compute routes.
    """
    from spacepilot.api.security import is_loopback_client, is_local_hostname

    client = request.client.host if request.client else None
    if not is_loopback_client(client):
        raise HTTPException(
            status_code=403,
            detail="The session token is issued to this machine only.",
        )
    origin = request.headers.get("origin")
    if origin and not is_local_hostname(origin.split("://", 1)[-1]):
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
