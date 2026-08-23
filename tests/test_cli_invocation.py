"""The CLI must work run as a file, not only as a module.

`python src/cli.py runtimes check mflux` raised ModuleNotFoundError: No module
named 'src' — running a script inside src/ puts src/ on sys.path rather than the
repo root, so the seven `from src.…` imports in cli.py cannot resolve. The
`python -m src.cli` form always worked, which is why the break went unnoticed.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "src/cli.py", "runtimes", "list"],
        [sys.executable, "-m", "src.cli", "runtimes", "list"],
    ],
    ids=["as-a-file", "as-a-module"],
)
def test_runtimes_list_runs_both_ways(argv):
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "No module named 'src'" not in proc.stderr


def test_measure_refuses_to_record_a_failed_run(tmp_path):
    """A command that exited non-zero measured nothing; recording it would poison
    the store with the duration of a crash."""
    proc = subprocess.run(
        [sys.executable, "src/cli.py", "measure", "--model", "demo",
         "--metric", "seconds_per_image", "--", "/bin/sh", "-c", "exit 3"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 3
    assert "nothing recorded" in proc.stdout


def test_measure_needs_a_command():
    proc = subprocess.run(
        [sys.executable, "src/cli.py", "measure", "--model", "demo",
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
    import src.cli as cli
    from src.pluto import measurements as ms

    written = []
    monkeypatch.setattr(ms, "write_system", lambda s, root=None: written.append(s))

    args = argparse.Namespace(
        model="demo", metric="seconds_per_image",
        command_argv=["--", "/bin/sh", "-c", "exit 3"],
    )
    assert cli.cmd_measure(args) == 3
    assert written == []
