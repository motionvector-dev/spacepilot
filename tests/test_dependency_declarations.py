"""Dependency declarations must agree, and CI must read one of them.

Two PRs in a row went red because .github/workflows/tests.yml carried its own
hand-typed pip install line. A dependency added to requirements.txt was never
installed, so a correctly-declared package still failed to import on the runner.
Silent drift between three lists is what these tests turn into a loud failure.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def _canonical(name: str) -> str:
    """PEP 503 name normalisation: PyYAML, pyyaml and py_yaml are one package."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_names(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        names.add(_canonical(re.split(r"[<>=!~\[; ]", line, 1)[0]))
    return names


def test_pyproject_dependencies_are_all_in_requirements():
    """pyproject declares what the package needs; CI installs requirements.txt.

    A package named in one and missing from the other means the app either
    fails to import on a runner or is under-declared to anyone installing it.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    declared = {
        _canonical(re.split(r"[<>=!~\[; ]", spec, 1)[0])
        for spec in pyproject["project"]["dependencies"]
    }
    installed = _requirement_names((ROOT / "requirements.txt").read_text())

    missing = sorted(declared - installed)
    assert not missing, (
        f"declared in pyproject.toml but absent from requirements.txt, so CI "
        f"never installs them: {missing}"
    )


def test_ci_installs_from_a_file_rather_than_a_hand_typed_list():
    """The regression itself: a pip install with package names typed inline.

    Any `pip install <name>` in the workflow is a second, private dependency
    list that nothing keeps in step with requirements.txt.
    """
    workflow = WORKFLOW.read_text()
    inline = [
        line.strip()
        for line in workflow.splitlines()
        if re.search(r"^\s*pip install\s+(?!-r\b|--upgrade pip\b|-e\b)\S", line)
    ]
    assert not inline, (
        "the CI workflow installs packages by name instead of from a "
        f"requirements file: {inline}"
    )
    assert "pip install -r requirements.txt" in workflow


def test_ci_does_not_install_the_gpu_stack():
    """requirements-gpu.txt is ~2.5 GB of CUDA wheels and the worker is stubbed.

    Naming the file in a comment is fine and expected; installing it is not.
    """
    installs = [
        line.strip()
        for line in WORKFLOW.read_text().splitlines()
        if "pip install" in line and "requirements-gpu.txt" in line
    ]
    assert not installs, f"CI installs the GPU stack: {installs}"
