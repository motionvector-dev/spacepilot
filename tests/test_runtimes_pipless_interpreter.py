"""Installing runtimes from an interpreter that has no pip.

The documented first run is `uv tool install spacepilot`. A uv-managed tool
venv ships no pip at all, so every `[python, "-m", "pip", "install", ...]`
died there -- which meant the released artifact could install none of its
`method: pip` runtimes, and mlx-lm (the only runtime behind the three models
that carry a route) was uninstallable.

These tests run against a real pip-less interpreter made by `uv venv`, not a
mock: the bug was about what a real interpreter does or does not have.
"""

import shutil
import subprocess

import pytest

from spacepilot import runtimes as rt
from spacepilot.runtimes import Impact, runtimes


UV = shutil.which("uv")
needs_uv = pytest.mark.skipif(not UV, reason="uv is not on PATH")


def shared_env_runtime():
    """A `method: pip` runtime that installs into the shared interpreter.

    Deliberately synthetic rather than a registry entry: the registry's own
    runtimes come and go and can become `isolated`, which would quietly stop
    these tests from exercising the shared-interpreter path at all.
    """
    return rt.parse_runtime({
        "schema": 1, "id": "shared-probe", "name": "Shared probe",
        "summary": "s", "license": "MIT", "serves": ["text"],
        "backends": ["metal"],
        "install": {"method": "pip", "package": "mlx-lm", "min_version": "0.31.3",
                    "checked": "2026-09-22",
                    "constraints": ["transformers>=5.12.1,<5.13"]},
        "verify": {"import": "mlx_lm"},
    }, "shared-probe.yaml")


@pytest.fixture(scope="module")
def pipless_python(tmp_path_factory):
    """A real interpreter with no pip, exactly like a uv tool venv."""
    if not UV:
        pytest.skip("uv is not on PATH")
    env = tmp_path_factory.mktemp("pipless") / "venv"
    subprocess.run([UV, "venv", str(env)], capture_output=True, text=True, check=True)
    py = env / "bin" / "python"
    probe = subprocess.run([str(py), "-m", "pip", "--version"],
                           capture_output=True, text=True)
    assert probe.returncode != 0, "this venv has pip; the fixture proves nothing"
    return str(py)


@needs_uv
def test_the_fixture_interpreter_really_has_no_pip(pipless_python):
    assert rt.pip_available(pipless_python) is False


@needs_uv
def test_install_command_falls_back_to_uv_for_a_pipless_interpreter(pipless_python):
    """`-m pip install` cannot run there, so it is not what we claim to run."""
    argv = rt.install_command(shared_env_runtime(), py=pipless_python)
    assert argv[:5] == [UV, "pip", "install", "--python", pipless_python]
    assert "mlx-lm>=0.31.3" in argv
    assert "-m" not in argv


@needs_uv
def test_install_dispatches_the_uv_command_not_pip(pipless_python, monkeypatch):
    """The command is not just constructed correctly, it is the one dispatched."""
    seen = []
    real_run = subprocess.run

    def spy(argv, *a, **kw):
        if isinstance(argv, list) and "install" in argv:
            seen.append(list(argv))

            class Done:
                returncode = 0
                stdout = ""
                stderr = ""
            return Done()
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(rt.subprocess, "run", spy)
    monkeypatch.setattr(rt, "check", lambda r, py=None, cfg=None: rt.Status(r.id, True, "0.0.0"))
    rt.install(shared_env_runtime(), py=pipless_python)

    assert seen, "no install command was dispatched"
    assert seen[-1][:5] == [UV, "pip", "install", "--python", pipless_python]


@needs_uv
def test_preview_dry_runs_through_uv_when_pip_is_absent(pipless_python, monkeypatch):
    seen = []
    real_run = subprocess.run

    def spy(argv, *a, **kw):
        seen.append(list(argv))
        if "--dry-run" in argv:
            class Done:
                returncode = 0
                stdout = ("Resolved 2 packages\n"
                          " - transformers==5.11.0\n"
                          " + transformers==5.12.1\n"
                          " + mlx-lm==0.31.3\n")
                stderr = ""
            return Done()
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(rt.subprocess, "run", spy)
    imp = rt.preview(shared_env_runtime(), py=pipless_python)

    dry = [c for c in seen if "--dry-run" in c][-1]
    assert dry[:5] == [UV, "pip", "install", "--python", pipless_python]
    assert imp.error is None
    assert ("mlx-lm", "0.31.3") in imp.new
    assert ("transformers", "5.11.0", "5.12.1") in imp.upgrades


@needs_uv
def test_uv_dry_run_output_reports_a_downgrade_as_a_downgrade():
    imp = rt._impact_from_uv_dry_run(
        " - opencv-python==5.0.0.93\n + opencv-python==4.14.0.94\n + mflux==0.19.0\n")
    assert imp.downgrades == [("opencv-python", "5.0.0.93", "4.14.0.94")]
    assert ("mflux", "0.19.0") in imp.new
    assert imp.is_disruptive


def test_a_fatal_preview_error_is_never_reported_as_harmless():
    """`is_disruptive: false` beside a fatal error is what misled MCP agents."""
    imp = Impact(error="No module named pip")
    assert imp.blocked is True
    assert imp.is_disruptive is True
    d = imp.to_dict()
    assert d["blocked"] is True and d["is_disruptive"] is True


@needs_uv
def test_with_neither_pip_nor_uv_the_error_names_a_command_to_run(pipless_python, monkeypatch):
    monkeypatch.setattr(rt.shutil, "which", lambda name: None)
    monkeypatch.setattr(rt, "_ensurepip", lambda py, timeout=300: False)

    imp = rt.preview(shared_env_runtime(), py=pipless_python)
    assert imp.blocked and imp.error
    assert "uv pip install" in imp.error
    assert pipless_python in imp.error

    st = rt.install(shared_env_runtime(), py=pipless_python)
    assert st.installed is False
    assert st.reason and "uv pip install" in st.reason


def test_script_installs_are_untouched_by_any_of_this():
    """A `method: script` runtime never asks an interpreter for pip."""
    script = [r for r in runtimes().values() if r.install.method == "script"]
    if not script:
        pytest.skip("no script-method runtime in the registry")
    argv = rt.install_command(script[0])
    assert argv[0] == "sh"
    assert rt.preview(script[0]).error is None


def test_the_mcp_preview_tool_passes_the_stop_signal_through(monkeypatch):
    """An MCP agent reads this dict and nothing else before installing."""
    from spacepilot import mcp_server

    monkeypatch.setattr(rt, "preview", lambda r, py=None: Impact(error="No module named pip"))
    out = mcp_server.spacepilot_preview_runtime_install("mlx-lm")
    assert out["blocked"] is True
    assert out["is_disruptive"] is True
    assert out["error"] == "No module named pip"
