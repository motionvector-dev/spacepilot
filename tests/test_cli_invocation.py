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
