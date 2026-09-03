"""Shared API dependencies and security gates."""

import time
import secrets
from typing import Optional
from fastapi import Header, HTTPException
from spacepilot.core.config import get_settings

_last_activity_time = time.time()


def update_activity() -> None:
    """Record activity to reset the idle watchdog timer."""
    global _last_activity_time
    _last_activity_time = time.time()


def get_last_activity_time() -> float:
    return _last_activity_time


def require_token(
    x_spacepilot_token: Optional[str] = Header(None, alias="X-SpacePilot-Token"),
    x_pluto_token: Optional[str] = Header(None, alias="X-Pluto-Token"),
) -> None:
    """Security gate accepting the canonical token plus one legacy header.

    If a client sends both spellings, it must send the same credential in each.
    That makes ambiguous proxy/client configuration fail closed instead of
    allowing one header to silently override the other.
    """
    settings = get_settings()
    try:
        if x_spacepilot_token is not None and x_pluto_token is not None:
            ok = (
                secrets.compare_digest(x_spacepilot_token, x_pluto_token)
                and secrets.compare_digest(x_spacepilot_token, settings.studio_token)
            )
        else:
            candidate = x_spacepilot_token if x_spacepilot_token is not None else x_pluto_token
            ok = bool(candidate) and secrets.compare_digest(candidate, settings.studio_token)
    except TypeError:
        # Headers decode as latin-1, and compare_digest rejects non-ASCII str.
        ok = False
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-SpacePilot-Token",
            headers={"WWW-Authenticate": "Token"},
        )


def require_speech_token(
    x_spacepilot_token: Optional[str] = Header(None, alias="X-SpacePilot-Token"),
) -> None:
    """Separate, narrower gate for `/api/speech/say` and
    `/api/speech/transcribe` only.

    These two routes are the ones actually reachable from the cross-origin
    demo pages listed in `Settings.cors_origins` (motionvector.dev,
    spacepilot.dev, the air-drums dev ports). `require_token`'s
    `studio_token` also unlocks the GPU shell websocket and every other
    compute route — handing that credential to anything CORS can reach was
    a standing local-RCE risk, so these two routes check a distinct,
    ephemeral `settings.speech_token` instead. Same header name as
    `require_token` (`X-SpacePilot-Token`) so a consumer's request shape
    does not change, only the value it must send.
    """
    settings = get_settings()
    ok = bool(x_spacepilot_token) and secrets.compare_digest(
        x_spacepilot_token, settings.speech_token)
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-SpacePilot-Token",
            headers={"WWW-Authenticate": "Token"},
        )
