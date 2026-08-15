#!/usr/bin/env python3
"""Auth tests for the LTX-2.5 resident GPU worker.

The worker imports the CUDA stack at module scope, which is not installed on
a Mac, so the GPU modules are stubbed. That keeps the security-critical auth
path testable off-GPU; nothing here touches inference.
"""

import os
import sys
import types
from pathlib import Path

import pytest

PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PLUTO_ROOT))
sys.path.append(str(PLUTO_ROOT / "src"))


def _stub_gpu_stack():
    for name in ["torch", "diffusers", "diffusers.utils", "transformers", "torchao", "torchao.quantization"]:
        module = sys.modules.setdefault(name, types.ModuleType(name))
        module.__getattr__ = lambda _attr: object  # any symbol resolves


@pytest.fixture(scope="module")
def worker(tmp_path_factory):
    """Import ltx_worker with a known token and a scratch output dir."""
    _stub_gpu_stack()
    os.environ["LOCAL_WORKER_TOKEN"] = "test-token"
    os.environ["LTX_OUTPUT_DIR"] = str(tmp_path_factory.mktemp("ltx-out"))
    sys.modules.pop("ltx_worker", None)
    import ltx_worker

    ltx_worker.app.config["TESTING"] = True
    return ltx_worker


@pytest.fixture()
def client(worker):
    return worker.app.test_client()


def test_missing_authorization_header_is_rejected(client, worker):
    """The old code treated a missing header as authorized. It must not."""
    worker._model_ready = True
    assert client.post("/generate", json={"prompt": "x"}).status_code == 401
    assert client.get("/status/anything").status_code == 401
    assert client.get("/download/anything").status_code == 401


def test_wrong_and_malformed_tokens_are_rejected(client):
    for header in ["Bearer local-dev-token", "Bearer wrong", "test-token", "Basic test-token", "", "Bearer "]:
        response = client.get("/status/anything", headers={"Authorization": header})
        assert response.status_code == 401, f"accepted {header!r}"


def test_correct_token_is_accepted(client, worker):
    """A valid token gets past auth; 404 here means the job simply does not exist."""
    response = client.get("/status/no-such-job", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


def test_empty_token_denies_everything(worker):
    """With no token configured the worker must refuse, not fall open."""
    original = worker.TOKEN
    try:
        worker.TOKEN = ""
        with worker.app.test_request_context("/status/x", headers={"Authorization": "Bearer "}):
            assert worker._authed() is False
        with worker.app.test_request_context("/status/x"):
            assert worker._authed() is False
    finally:
        worker.TOKEN = original


def test_download_does_not_escape_output_dir(client, worker):
    """A job id must not walk out of OUTPUT_DIR."""
    secret = PLUTO_ROOT / "pytest_worker_marker.txt"
    secret.write_text("should never be served")
    try:
        response = client.get(
            "/download/../../pytest_worker_marker",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 404
    finally:
        secret.unlink()
