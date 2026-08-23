"""Shared API dependencies and security gates."""

import time
import secrets
from typing import Optional
from fastapi import Header, HTTPException
from spacepilot.pluto.core.config import get_settings

_last_activity_time = time.time()


def update_activity() -> None:
    """Record activity to reset the idle watchdog timer."""
    global _last_activity_time
    _last_activity_time = time.time()


def get_last_activity_time() -> float:
    return _last_activity_time


def require_token(x_pluto_token: Optional[str] = Header(None)) -> None:
    """Security gate for mutating compute operations."""
    settings = get_settings()
    try:
        ok = bool(x_pluto_token) and secrets.compare_digest(x_pluto_token, settings.studio_token)
    except TypeError:
        # Headers decode as latin-1, and compare_digest rejects non-ASCII str.
        ok = False
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-Pluto-Token",
            headers={"WWW-Authenticate": "Token"},
        )
