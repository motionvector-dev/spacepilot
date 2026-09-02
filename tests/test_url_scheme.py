"""A URL from configuration must not be able to turn an HTTP call into a file read.

`urllib.request.urlopen` served `file://` as happily as `http://`. These tests
pin the replacement: only http and https get past `require_http_url`, and
`mlx_generate_audio` — whose base URL comes from the MLX_SERVE_URL environment
variable — refuses anything else before it builds a request.
"""

import pytest

from spacepilot.core import config
from spacepilot.core.http import UnsupportedURLScheme, require_http_url
from spacepilot.services.audio import mlx_generate_audio


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "FILE:///etc/passwd",
        "ftp://example.invalid/x",
        "data:text/plain,hello",
        "/etc/passwd",
        "gopher://example.invalid",
    ],
)
def test_require_http_url_rejects_non_http_schemes(url):
    with pytest.raises(UnsupportedURLScheme):
        require_http_url(url)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:11234/v1/audio", "https://example.invalid/v1/audio"],
)
def test_require_http_url_accepts_http_and_https(url):
    assert require_http_url(url) == url


def test_require_http_url_rejects_url_without_host():
    with pytest.raises(UnsupportedURLScheme):
        require_http_url("http:///v1/audio")


def test_mlx_generate_audio_refuses_a_file_url(monkeypatch, tmp_path):
    """The old urlopen path read this file off disk and returned its bytes."""
    secret = tmp_path / "secret.txt"
    secret.write_text("not a wav file")

    monkeypatch.setattr(config, "_settings_instance", None)
    monkeypatch.setenv("MLX_SERVE_URL", f"file://{secret}")
    with pytest.raises(UnsupportedURLScheme):
        mlx_generate_audio("", {"prompt": "x"}, timeout=5)
