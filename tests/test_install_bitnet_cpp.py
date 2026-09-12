"""tools/install-bitnet-cpp.sh: the missing-GGUF guard.

`setup_env.py --model-dir <dir> -q i2_s` always runs a full CMake build of
the bundled llama.cpp fork before it ever looks at whether the GGUF is
there -- so a directory that hasn't been fetched yet used to fail deep
inside that build with a confusing CMake/setup_env error, minutes in.

These tests prove the script fails fast, before any clone or build, with a
message that actually names the missing file and how to get it -- never by
letting a real `git clone` run (that would hang or hit the network in CI).
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "install-bitnet-cpp.sh"


@pytest.fixture
def no_git_path(tmp_path):
    """A PATH with no `git` on it, so the script cannot possibly clone
    anything even if the guard regresses -- the fast-fail assertion below
    would otherwise be trusting a slow network hang to time out just right."""
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    real_path = os.environ.get("PATH", "")
    kept = [p for p in real_path.split(os.pathsep) if p and not (Path(p) / "git").exists()]
    return os.pathsep.join([str(fake_bin), *kept])


def test_fails_fast_when_the_gguf_is_missing(tmp_path, no_git_path):
    gguf_dir = tmp_path / "model-dir"
    gguf_dir.mkdir()
    bitnet_dir = tmp_path / "bitnet-cpp-home"

    env = dict(os.environ)
    env["PATH"] = no_git_path
    env["BITNET_CPP_DIR"] = str(bitnet_dir)

    start = time.monotonic()
    proc = subprocess.run(
        ["bash", str(SCRIPT), str(gguf_dir)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    elapsed = time.monotonic() - start

    assert proc.returncode != 0, (
        f"expected a non-zero exit for a dir with no GGUF, got 0; "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "ggml-model-i2_s.gguf" in proc.stderr
    assert "fetch" in proc.stderr.lower() or "fly.py run" in proc.stderr

    assert elapsed < 2.0, f"guard should fail before any clone/build, took {elapsed:.2f}s"
    assert not bitnet_dir.exists(), "no bitnet.cpp checkout should be created by a fast-fail"


def test_succeeds_past_the_guard_when_the_gguf_is_present(tmp_path, no_git_path):
    """Sanity check on the guard's own condition: once the file is there,
    the script must not stop at this check. It will still fail later, for
    unrelated reasons (no real git/cmake reachable here), but not with the
    missing-GGUF message."""
    gguf_dir = tmp_path / "model-dir"
    gguf_dir.mkdir()
    (gguf_dir / "ggml-model-i2_s.gguf").write_bytes(b"not a real gguf, just a marker")
    bitnet_dir = tmp_path / "bitnet-cpp-home"

    env = dict(os.environ)
    env["PATH"] = no_git_path
    env["BITNET_CPP_DIR"] = str(bitnet_dir)

    proc = subprocess.run(
        ["bash", str(SCRIPT), str(gguf_dir)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert proc.returncode != 0  # still fails -- git is unavailable on PATH
    assert "fetch it first" not in proc.stderr
    assert "ggml-model-i2_s.gguf" not in proc.stderr
