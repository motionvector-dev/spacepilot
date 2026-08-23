"""Outbound HTTP that cannot be talked into reading a local file.

`urllib.request.urlopen` honours `file://`, `ftp://` and `data:` as readily as
`http://`. Anywhere a URL reaches it from configuration, a request body, or a
model response, an apparent network call is one scheme away from a local-file
read. `httpx` speaks only HTTP(S), so migrating removes that reach; the explicit
check here turns a bad scheme into a clear error at the call site instead of an
`httpx.UnsupportedProtocol` from deep in the transport.

Keep this module free of fastapi and of anything else the standalone scripts do
not already import.
"""

from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsupportedURLScheme(ValueError):
    """Raised when a URL is not plain HTTP or HTTPS."""


def require_http_url(url: str) -> str:
    """Return `url` unchanged, or raise if it is not an absolute http(s) URL."""
    parsed = urlparse(str(url))
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsupportedURLScheme(
            f"refusing non-HTTP URL scheme {parsed.scheme or '(none)'!r}: "
            f"only {', '.join(sorted(ALLOWED_SCHEMES))} are allowed"
        )
    if not parsed.netloc:
        raise UnsupportedURLScheme(f"URL has no host: {url!r}")
    return url
