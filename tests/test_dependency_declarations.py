"""Dependency declarations must agree, and CI must read one of them.

Two PRs in a row went red because .github/workflows/tests.yml carried its own
hand-typed pip install line. A dependency added to requirements.txt was never
installed, so a correctly-declared package still failed to import on the runner.
Silent drift between three lists is what these tests turn into a loud failure.

The lists agreeing with each other is only half of it. All three can agree and
still be wrong together, which is what happened: `flask`, `Pillow`, `packaging`,
`python-multipart` and `starlette` were imported by shipped code and declared in
no list at all, so a clean `pipx install` produced a CLI whose image paths raised
ModuleNotFoundError at the moment of use. The last two tests here read the
imports out of the source, so the source is what has to agree.
"""

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
PACKAGE = ROOT / "spacepilot"

# Import name on the left, distribution name on the right, for the cases where
# the two differ. Anything absent from here is assumed to match.
DISTRIBUTION = {
    "PIL": "pillow",
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "multipart": "python-multipart",
    "kokoro_onnx": "kokoro-onnx",
    "llama_cpp": "llama-cpp-python",
    "dateutil": "python-dateutil",
}

# Runtimes the user installs on purpose through `spacepilot runtimes install`,
# which is why they are imported lazily and declared nowhere. `runtimes list`
# reports each as available or unusable; a missing one is a state the CLI
# describes, not a packaging bug. Keep this list short and justified.
RUNTIME_MANAGED = {
    "llama_cpp",
    "mlx_audio",
    "mlx_video",
    "mflux",
}


def _imports_under(package: Path) -> dict[str, list[tuple[str, bool]]]:
    """Every non-stdlib, non-local module imported under `package`.

    Each site records whether the import sits inside a function, because a
    lazily-imported optional runtime is a deliberate pattern here and a
    module-level one is not.
    """
    stdlib = set(sys.stdlib_module_names)
    found: dict[str, list[tuple[str, bool]]] = {}
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        nested = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nested.update(id(child) for child in ast.walk(node))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [] if node.level else [node.module or ""]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                if not top or top in stdlib or top == "spacepilot":
                    continue
                site = f"{path.relative_to(ROOT)}:{node.lineno}"
                found.setdefault(top, []).append((site, id(node) in nested))
    return found


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


def test_every_imported_module_is_declared_somewhere():
    """The direction the other tests cannot see: source against declaration.

    `test_pyproject_dependencies_are_all_in_requirements` compares two lists to
    each other. Both can omit the same package and still agree, which is exactly
    how `flask` and `Pillow` reached a release undeclared.
    """
    imports = _imports_under(PACKAGE)
    assert len(imports) >= 10, (
        f"only {len(imports)} third-party imports found under {PACKAGE}; the "
        "extractor is broken, and an empty set would pass against anything"
    )

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    specs = list(pyproject.get("dependencies", []))
    for extra in pyproject.get("optional-dependencies", {}).values():
        specs.extend(extra)
    declared = {_canonical(re.split(r"[<>=!~\[; ]", spec, 1)[0]) for spec in specs}

    undeclared = {
        module: [site for site, _ in sites]
        for module, sites in imports.items()
        if module not in RUNTIME_MANAGED
        and _canonical(DISTRIBUTION.get(module, module)) not in declared
    }

    assert not undeclared, (
        "imported by shipped code and declared in no dependency group, so a "
        "clean install raises ModuleNotFoundError at the moment of use:\n"
        + "\n".join(
            f"  {module} — {', '.join(sites[:3])}"
            for module, sites in sorted(undeclared.items())
        )
    )


@pytest.mark.parametrize("module", sorted(RUNTIME_MANAGED))
def test_runtime_managed_modules_are_imported_lazily(module):
    """A runtime the user opts into must not be imported when the CLI starts.

    `spacepilot runtimes list` has to report `llama-cpp` as absent. It cannot do
    that if importing the driver raises first, so these imports stay inside the
    function that needs them. This is also what earns their absence from the
    dependency lists above.
    """
    offenders = [
        site for site, nested in _imports_under(PACKAGE).get(module, []) if not nested
    ]
    assert not offenders, (
        f"{module} is installed on request through `spacepilot runtimes install`, "
        f"so importing it at module level makes the CLI unusable when it is "
        f"absent instead of reporting it as absent: {offenders}"
    )
