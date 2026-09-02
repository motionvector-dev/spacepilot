"""Keeping a local server local.

This server hands out a token that unlocks everything, including a websocket
that opens a shell. Four things have to hold for that to be safe, and none of
them held:

1. It must listen on the loopback interface only. The default was 0.0.0.0, so
   `spacepilot serve` published the API to every interface — on shared wifi, anyone
   who could reach the port could read the token and open the shell.

2. It must reject requests carrying a foreign Host header. Without that, DNS
   rebinding defeats CORS: an attacker's domain re-resolves to 127.0.0.1, the
   browser then treats their page as same-origin, and reads the token.

3. Websockets need their own origin check. CORS does not apply to them at all —
   a page on any origin may open a websocket to localhost and will only be
   stopped by whatever the handler itself verifies.

4. The token endpoint must answer loopback callers only. It is the key to every
   other gate, so it should not be reachable even if the bind is widened later.
"""

from __future__ import annotations

import ipaddress
from typing import Iterable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket

# nosec B104 - this is an allowlist of hostnames that mean "this machine",
# not a bind address. The literal is what LocalOnlyMiddleware compares an
# incoming Host header against; it opens nothing.
LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "testserver"}  # nosec B104

# Hostnames that resolve to this machine and are used deliberately. Anything
# ending in .localhost is loopback by RFC 6761 and browsers honour it.
LOCAL_SUFFIXES = (".localhost",)


def _hostname(host_header: str) -> str:
    """Strip the port, and the brackets IPv6 literals carry."""
    h = (host_header or "").strip()
    if h.startswith("["):
        return h[1 : h.find("]")] if "]" in h else h
    return h.rsplit(":", 1)[0] if ":" in h and h.count(":") == 1 else h


def is_local_hostname(host_header: str) -> bool:
    name = _hostname(host_header).lower()
    if not name:
        return False
    if name in LOOPBACK_HOSTNAMES:
        return True
    if name.endswith(LOCAL_SUFFIXES):
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def is_loopback_client(client_host: Optional[str]) -> bool:
    if not client_host:
        return False
    try:
        return ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        return client_host == "testclient"  # starlette's TestClient


def origin_allowed(origin: Optional[str], allowed: Iterable[str]) -> bool:
    """A websocket handshake's Origin, checked by hand because CORS will not.

    An absent Origin is allowed: non-browser clients (the CLI, a test, an MCP
    server) do not send one, and they are not the threat this defends against —
    a page in the user's browser is.
    """
    if origin is None:
        return True
    if origin in set(allowed):
        return True
    return is_local_hostname(origin.split("://", 1)[-1])


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    """Reject anything whose Host header is not this machine.

    This is the DNS-rebinding defence. The attack works by making the browser
    believe an attacker-controlled name is the local server, which sidesteps
    every origin check — but the Host header still carries their name, and this
    machine was never called that.
    """

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        if self.enabled and not is_local_hostname(request.headers.get("host", "")):
            return JSONResponse(
                status_code=421,  # Misdirected Request
                content={
                    "detail": "This server answers to localhost only. The Host header "
                              f"{request.headers.get('host', '')!r} is not one of its names."
                },
            )
        return await call_next(request)


async def websocket_is_local(ws: WebSocket, allowed_origins: Iterable[str]) -> bool:
    """Check a websocket handshake before accepting it.

    Call this first in a websocket handler. Returning False means close without
    accepting — the connection should never reach the authentication frame.
    """
    if not is_local_hostname(ws.headers.get("host", "")):
        return False
    return origin_allowed(ws.headers.get("origin"), allowed_origins)
