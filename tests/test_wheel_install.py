"""The test the other 369 could not be: does the built wheel actually work?

Every other test in this suite runs against a source checkout, where the
registry sits at a path `Path(__file__).parents[2]` happens to find and every
directory is writable. That is why v2.8.0 shipped with `spacepilot models`
exiting 1 on `registry directory not found` and `spacepilot measure` writing
records into site-packages: nothing here had ever seen an installed copy.

So this builds the wheel, installs it into a throwaway venv, and runs the CLI
the way a user would. It is slow and it needs the network to fetch the build
backend, so it is marked `packaging` and deselected from the default run —
`pytest -m packaging` runs it, and CI gives it its own job.

The venv is created with `--system-site-packages` and the wheel installed with
`--no-deps`, so the runtime dependencies come from the environment that is
already installed rather than being downloaded again. What is under test is the
wheel's own contents and the paths the code resolves, and neither depends on
where fastapi came from. `test_the_installed_package_is_the_one_under_test`
guards the one thing that arrangement could hide.
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

ROOT = Path(__file__).resolve().parents[1]

# A model and a runtime that ship in the registry. If either is renamed this
# test should be updated, not deleted — the point is to prove real catalogue
# content survives the trip into the wheel.
A_SHIPPED_MODEL = "kokoro-82m-onnx"
A_SHIPPED_RUNTIME = "mflux"


@pytest.fixture(scope="module")
def wheel(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("wheel")
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(out), str(ROOT)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.fail(f"building the wheel failed:\n{proc.stdout}\n{proc.stderr}")
    wheels = list(out.glob("spacepilot-*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"
    return wheels[0]


@pytest.fixture(scope="module")
def install(tmp_path_factory, wheel):
    """A venv with the wheel in it, plus a fake HOME.

    HOME is redirected rather than `$SPACEPILOT_DATA_DIR` set, because the
    default path is exactly what is under test: setting the override would
    prove only that the override works, which is not the bug that shipped.
    """
    base = tmp_path_factory.mktemp("install")
    venv = base / "venv"
    home = base / "home"
    cwd = base / "cwd"        # never the repo: a `spacepilot/` in the working
    home.mkdir()              # directory shadows the installed package
    cwd.mkdir()

    subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True)
    bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    proc = subprocess.run(
        [str(bin_dir / "python"), "-m", "pip", "install", "--no-deps", "--quiet", str(wheel)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.fail(f"installing the wheel failed:\n{proc.stdout}\n{proc.stderr}")

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "SPACEPILOT_DATA_DIR")}
    env["HOME"] = str(home)
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(bin_dir / args[0]), *args[1:]],
                              capture_output=True, text=True, cwd=str(cwd), env=env)

    located = run("python", "-c", "import spacepilot, os; print(os.path.dirname(spacepilot.__file__))")
    assert located.returncode == 0, located.stderr
    package_dir = Path(located.stdout.strip())

    class Install:
        pass

    inst = Install()
    inst.run = run
    inst.venv = venv
    inst.home = home
    inst.package_dir = package_dir
    return inst


def test_the_installed_package_is_the_one_under_test(install):
    """`--system-site-packages` means an outer spacepilot could win the import
    and quietly make every assertion below meaningless."""
    assert install.venv in install.package_dir.parents, (
        f"imported spacepilot from {install.package_dir}, which is outside the test venv")


def test_the_wheel_stays_a_single_top_level_package(wheel):
    """#43: setuptools flattened the tree into sixteen generic top-level
    modules — `cli`, `engines`, `web_api` — and installing the package put them
    all on the import path."""
    with zipfile.ZipFile(wheel) as z:
        name = next(n for n in z.namelist() if n.endswith("top_level.txt"))
        assert z.read(name).decode().split() == ["spacepilot"]


def test_the_wheel_exposes_only_spacepilot_commands(wheel):
    with zipfile.ZipFile(wheel) as z:
        name = next(n for n in z.namelist() if n.endswith("entry_points.txt"))
        entry_points = z.read(name).decode()
    assert "spacepilot = spacepilot.cli:main" in entry_points
    assert "spacepilot-mcp = spacepilot.mcp_server:main" in entry_points
    assert "\npluto =" not in entry_points


def test_the_wheel_carries_the_registry(wheel):
    """The whole defect in one assertion: the shipped wheel had zero of these."""
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
    models = [n for n in names if n.startswith("spacepilot/registry/models/") and n.endswith(".yaml")]
    runtimes = [n for n in names if n.startswith("spacepilot/registry/runtimes/") and n.endswith(".yaml")]
    assert len(models) >= 15, f"only {len(models)} model files in the wheel"
    assert len(runtimes) >= 5, f"only {len(runtimes)} runtime files in the wheel"


def test_models_lists_models(install):
    proc = install.run("spacepilot", "models")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert A_SHIPPED_MODEL in proc.stdout


def test_runtimes_lists_runtimes(install):
    proc = install.run("spacepilot", "runtimes")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert A_SHIPPED_RUNTIME in proc.stdout


def test_doctor_runs(install):
    proc = install.run("spacepilot", "doctor")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_the_shipped_measurement_corpus_is_readable(install):
    """A fresh install sees the records that came with it, not an empty store."""
    proc = install.run(
        "python", "-c",
        "from spacepilot.measurements import load_measurements;"
        "print(len(load_measurements()))")
    assert proc.returncode == 0, proc.stderr
    assert int(proc.stdout.strip()) > 0, "the shipped corpus read as empty"


def test_measure_writes_outside_site_packages(install):
    """Records used to land in site-packages, where they are invisible,
    unbackuped, and destroyed by the next reinstall."""
    registry = install.package_dir / "registry"
    before = {p: p.stat().st_mtime for p in registry.rglob("*")}

    proc = install.run(
        "spacepilot", "measure", "--model", A_SHIPPED_MODEL,
        "--metric", "seconds_per_image", "--", sys.executable, "-c", "pass")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"

    after = {p: p.stat().st_mtime for p in registry.rglob("*")}
    assert after == before, "measure touched the installed package"

    written = sorted(install.home.rglob("registry/measurements/**/*.yaml"))
    assert written, f"no record under the user data directory\n{proc.stdout}"
    for path in written:
        assert install.package_dir not in path.parents

    systems = sorted(install.home.rglob("registry/systems/*.yaml"))
    assert systems, "the system record went somewhere else than the measurement"


@pytest.fixture(scope="module")
def isolated_install(tmp_path_factory, wheel):
    """The wheel in a venv of its own, with its declared dependencies resolved.

    The `install` fixture above deliberately uses `--system-site-packages` and
    `--no-deps`, which makes it fast and lets it prove the *contents* of the
    wheel. The cost is that it borrows every third-party module from the outer
    environment, so a package the wheel imports but never declares still works
    there — and CI populates that outer environment from requirements.txt, which
    is how `flask`, `Pillow`, `packaging`, `python-multipart` and `starlette`
    reached a release undeclared with this job green.

    This fixture resolves dependencies from the wheel's own metadata and nothing
    else, so an undeclared import has nowhere to come from.
    """
    base = tmp_path_factory.mktemp("isolated")
    venv = base / "venv"
    home = base / "home"
    cwd = base / "cwd"
    home.mkdir()
    cwd.mkdir()

    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    proc = subprocess.run(
        [str(bin_dir / "python"), "-m", "pip", "install", "--quiet", str(wheel)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.fail(
            "installing the wheel with its declared dependencies failed:\n"
            f"{proc.stdout}\n{proc.stderr}"
        )

    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "SPACEPILOT_DATA_DIR")}
    env["HOME"] = str(home)
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(bin_dir / args[0]), *args[1:]],
                              capture_output=True, text=True, cwd=str(cwd), env=env)

    return run


def test_the_cli_runs_with_only_its_declared_dependencies(isolated_install):
    """What a `pip install spacepilot` or `pipx install spacepilot` actually gets.

    Every other test in this file runs against an environment that carries more
    than the wheel asks for.
    """
    for command in (["doctor"], ["models", "list"], ["runtimes", "list"]):
        proc = isolated_install("spacepilot", *command)
        assert proc.returncode == 0, (
            f"`spacepilot {' '.join(command)}` exited {proc.returncode} on an "
            f"install carrying only the wheel's declared dependencies:\n{proc.stderr}"
        )


def test_no_shipped_module_imports_something_undeclared(isolated_install):
    """Import every module in the wheel, on an install with nothing borrowed.

    This catches a **module-level** import of an undeclared package, which the
    CLI smoke test above can miss: a module the CLI never loads still ships, and
    still breaks whoever imports it.

    It does NOT catch a lazily-imported one. `Pillow` sits inside functions in
    `spacepilot/services/image_utils.py` and `spacepilot/api/routes/generate.py`, so every
    module here imports cleanly without it and this test stays green — which is
    exactly how Pillow reached a release undeclared.  Removing Pillow from
    pyproject.toml was verified to leave this test passing.
    `tests/test_dependency_declarations.py` is what covers that direction: it
    reads the imports out of the source, so where the import sits does not
    matter.  The two tests are a pair; neither is sufficient alone.
    """
    script = (
        "import importlib, pkgutil, sys, spacepilot\n"
        "bad = []\n"
        "for m in pkgutil.walk_packages(spacepilot.__path__, 'spacepilot.'):\n"
        "    try:\n"
        "        importlib.import_module(m.name)\n"
        "    except ModuleNotFoundError as e:\n"
        "        bad.append(f'{m.name}: {e.name}')\n"
        "    except Exception:\n"
        "        pass\n"   # anything that is not a missing module is another test's problem
        "print('\\n'.join(bad))\n"
    )
    proc = isolated_install("python", "-c", script)
    assert proc.returncode == 0, proc.stderr

    # `spacepilot.ltx_worker` is the GPU worker. It imports flask, torch,
    # diffusers, transformers and torchao at module level and is installed from
    # the `gpu-worker` extra on the box, never as part of a normal install.
    missing = [
        line for line in proc.stdout.strip().splitlines()
        if line and not line.startswith("spacepilot.ltx_worker:")
    ]
    assert not missing, (
        "modules in the wheel that cannot import on a clean install — each is a "
        "dependency that is used but not declared:\n  " + "\n  ".join(missing)
    )
