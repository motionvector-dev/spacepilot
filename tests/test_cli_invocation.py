"""The CLI must work run as a file, not only as a module.

`python spacepilot/cli.py runtimes check mflux` raised ModuleNotFoundError: No module
named 'spacepilot' — running a script inside the package puts that directory on
sys.path rather than the repo root, so the seven `from spacepilot.…` imports in
cli.py cannot resolve. The
`python -m spacepilot.cli` form always worked, which is why the break went unnoticed.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "spacepilot/cli.py", "runtimes", "list"],
        [sys.executable, "-m", "spacepilot.cli", "runtimes", "list"],
    ],
    ids=["as-a-file", "as-a-module"],
)
def test_runtimes_list_runs_both_ways(argv):
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "No module named 'spacepilot'" not in proc.stderr


def test_measure_refuses_to_record_a_failed_run(tmp_path):
    """A command that exited non-zero measured nothing; recording it would poison
    the store with the duration of a crash."""
    proc = subprocess.run(
        [sys.executable, "spacepilot/cli.py", "measure", "--model", "demo",
         "--metric", "seconds_per_image", "--", "/bin/sh", "-c", "exit 3"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 3
    assert "nothing recorded" in proc.stdout


def test_measure_needs_a_command():
    proc = subprocess.run(
        [sys.executable, "spacepilot/cli.py", "measure", "--model", "demo",
         "--metric", "seconds_per_image"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 1
    assert "Nothing to measure" in proc.stdout


def test_a_failed_measure_leaves_no_system_record(monkeypatch):
    """"nothing recorded" has to mean nothing.

    The system record was written before the command ran, so every failed
    measure still stamped the host into registry/systems/. On CI that put the
    runner's own Xeon into the shipped registry and broke the export test.
    """
    import argparse

    sys.path.insert(0, str(ROOT))
    import spacepilot.cli as cli
    from spacepilot.pluto import measurements as ms

    written = []
    monkeypatch.setattr(ms, "write_system", lambda s, root=None: written.append(s))

    args = argparse.Namespace(
        model="demo", metric="seconds_per_image",
        command_argv=["--", "/bin/sh", "-c", "exit 3"],
    )
    assert cli.cmd_measure(args) == 3
    assert written == []


def _cli(*argv):
    return subprocess.run([sys.executable, "spacepilot/cli.py", *argv],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_models_list_lists_the_registry():
    """`spacepilot models list` is documented, and parsed `list` as a model id.

    `runtimes list` worked, so the two commands disagreed with each other.
    """
    proc = _cli("models", "list")
    assert proc.returncode == 0, proc.stdout + proc.stderr[-2000:]
    assert "VERDICT" in proc.stdout
    assert "kokoro-82m-onnx" in proc.stdout


def test_bare_models_lists_the_registry():
    proc = _cli("models")
    assert proc.returncode == 0, proc.stdout + proc.stderr[-2000:]
    assert "VERDICT" in proc.stdout
    assert "kokoro-82m-onnx" in proc.stdout


def test_models_with_an_id_shows_that_one_model():
    proc = _cli("models", "kokoro-82m-onnx")
    assert proc.returncode == 0, proc.stdout + proc.stderr[-2000:]
    assert "[kokoro-82m-onnx]" in proc.stdout
    assert "licence" in proc.stdout
    assert "VERDICT" not in proc.stdout


def test_an_unknown_model_id_fails_and_names_the_installed_binary():
    proc = _cli("models", "not-a-real-model")
    assert proc.returncode != 0
    assert "not-a-real-model" in proc.stdout
    assert "spacepilot models" in proc.stdout
    assert "pluto models" not in proc.stdout


def test_no_model_variant_is_named_list():
    """`models list` reserves the word, so a variant called `list` would become
    unreachable by id."""
    sys.path.insert(0, str(ROOT))
    from spacepilot.pluto.registry import registry

    assert [v.id for v in registry().variants if v.id == "list"] == []
