"""Runtimes are installed, not downloaded, so the promises differ.

What matters here is not where a number came from but whether the package is
really importable in the interpreter this project uses, and whether installing
it would quietly change something else.
"""

import sys

import pytest

from spacepilot.runtimes import (
    BACKENDS, MODALITIES, Impact, RuntimeError_, load_runtimes, parse_runtime, runtimes,
)


def test_registry_loads_and_ids_are_unique():
    rs = load_runtimes()
    assert rs
    assert len(rs) == len({r.id for r in rs.values()})


def test_every_runtime_declares_how_to_verify_itself():
    """A runtime with no import (or, for a script install, no binary) to try
    cannot be checked, only assumed."""
    for r in runtimes().values():
        if r.install.method == "script":
            assert r.verify_binary, f"{r.id}: no binary to verify with"
        else:
            assert r.verify_import, f"{r.id}: no import to verify with"
        assert r.install.package
        assert set(r.serves) <= MODALITIES
        assert set(r.backends) <= BACKENDS


def test_pinned_versions_record_when_they_were_checked():
    for r in runtimes().values():
        if r.install.min_version:
            assert r.install.checked, f"{r.id}: pins a version with no checked date"


def test_check_reports_a_reason_when_a_runtime_is_absent(monkeypatch):
    """Absence must carry the import error, not a bare False."""
    from spacepilot import runtimes as rt
    r = runtimes()["mflux"]
    st = rt.check(r)
    if not st.installed:
        assert st.reason, "an uninstalled runtime must say why"
        assert "ModuleNotFound" in st.reason or "No module" in st.reason


def test_outdated_is_not_the_same_as_installed():
    """A package that imports but predates the pinned version is its own state.

    A caller checking only `installed` would run against an API that may not
    exist in the version actually present.
    """
    from spacepilot import runtimes as rt
    for r in runtimes().values():
        st = rt.check(r)
        if st.below_minimum:
            assert st.installed, "below_minimum only applies to something present"
            assert st.reason and r.install.min_version in st.reason
            return
    pytest.skip("nothing installed is currently below its pinned minimum")


def test_python_incompatibility_is_reported_rather_than_attempted():
    """stable-audio-tools pins itself below 3.11; this project runs 3.11."""
    from spacepilot import runtimes as rt
    r = runtimes()["stable-audio-tools"]
    ok, note = rt.python_ok(r)
    if not ok:
        assert "Python" in note
        st = rt.check(r)
        assert st.python_compatible is False
        assert st.python_note


def test_a_downgrade_counts_as_disruptive():
    """Resolving mflux lowers opencv-python. Nothing in the request says so."""
    imp = Impact(downgrades=[("opencv-python", "5.0.0.93", "4.14.0.94")])
    assert imp.is_disruptive
    assert not Impact(new=[("mflux", "0.19.0")]).is_disruptive
    assert not Impact(upgrades=[("mlx", "0.31.2", "0.32.1")]).is_disruptive


def test_install_command_names_the_interpreter():
    """A runtime installed into some other Python is not installed here."""
    from spacepilot import runtimes as rt
    argv = rt.install_command(runtimes()["mflux"], py="/tmp/fake-python")
    assert argv[0] == "/tmp/fake-python"
    assert argv[1:4] == ["-m", "pip", "install"]
    assert argv[-1].startswith("mflux>=")


def test_configured_interpreter_wins_over_the_calling_pipx_python(monkeypatch):
    """A pipx CLI must execute runtimes in the configured ML environment."""
    from spacepilot import runtimes as rt

    monkeypatch.delenv("SPACEPILOT_PYTHON", raising=False)
    monkeypatch.delenv("PLUTO_PYTHON", raising=False)
    assert rt.interpreter({"python_bin": "/opt/spacepilot/ml/bin/python"}) == \
        "/opt/spacepilot/ml/bin/python"


def test_mlx_lm_install_carries_the_known_good_transformers_constraint():
    from spacepilot import runtimes as rt

    runtime = runtimes()["mlx-lm"]
    assert runtime.install.constraints == ["transformers>=5.12.1,<5.13"]
    # mlx-lm is `isolated` now, so an explicit `py` is ignored on purpose --
    # the whole point is that it never resolves into a shared interpreter.
    argv = rt.install_command(runtime, py="/tmp/python")
    assert argv[0] == str(rt.isolated_python(runtime))
    assert argv[-2:] == ["mlx-lm>=0.31.3", "transformers>=5.12.1,<5.13"]


def test_unknown_backend_is_rejected():
    bad = {
        "schema": 1, "id": "x", "name": "X", "summary": "s", "license": "MIT",
        "serves": ["image"], "backends": ["vulkan"],
        "install": {"method": "pip", "package": "x"}, "verify": {"import": "x"},
    }
    with pytest.raises(RuntimeError_, match="unknown backends"):
        parse_runtime(bad, "bad.yaml")


def test_unknown_install_method_is_rejected():
    bad = {
        "schema": 1, "id": "x", "name": "X", "summary": "s", "license": "MIT",
        "serves": ["image"], "backends": ["cpu"],
        "install": {"method": "curl-bash", "package": "x"}, "verify": {"import": "x"},
    }
    with pytest.raises(RuntimeError_, match="method"):
        parse_runtime(bad, "bad.yaml")


def test_check_finds_a_runtime_installed_in_its_own_environment(tmp_path, monkeypatch):
    """mflux is reached as a subprocess from its own env, never imported here.

    An import check against this interpreter says "missing" while `run image`
    executes it fine; the external-binary route is what makes the two verbs
    agree. The fake bin dir stands in for the conda env; /usr/bin/false stands
    in for an interpreter where the import fails.
    """
    from spacepilot import runtimes as rt
    r = runtimes()["mflux"]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "mflux-generate"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("SPACEPILOT_MFLUX_BIN", str(bin_dir))

    st = rt.check(r, py="/usr/bin/false")
    assert st.installed
    assert st.external
    assert st.external_path == str(exe)
    assert st.version == "unknown"  # no python in the fake env to ask


def test_external_route_requires_the_binary_to_actually_exist(tmp_path, monkeypatch):
    """A configured bin dir with no entry point in it is still not installed."""
    from spacepilot import runtimes as rt
    r = runtimes()["mflux"]
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("SPACEPILOT_MFLUX_BIN", str(empty))

    st = rt.check(r, py="/usr/bin/false")
    assert not st.installed
    assert not st.external
    assert st.external_path is None
    assert st.reason


# --------------------------------------------------------- interpreter truth
#
# One truth for "where does a runtime live": `fly.py plan` and `spacepilot
# runtimes list` must resolve the *same* interpreter for a shared-interpreter
# (non-isolated, non-external) pip runtime, regardless of which process asks.
# Before this fix, `interpreter()` fell back to `sys.executable` -- the
# interpreter of whoever imports this module -- which differed between the
# pipx-installed `spacepilot` console script (correct by accident) and
# `tools/fly.py` (normally launched as `python3 tools/fly.py`, the ambient
# interpreter, not the one `spacepilot run <cli>` actually subprocesses
# into). See docs/registry/flights.md's "PR #137" note for the real
# incident this reproduces.

def test_spacepilot_console_python_reads_the_pipx_shim(tmp_path):
    from spacepilot import runtimes as rt

    fake_bin_dir = tmp_path / "pipx" / "venvs" / "spacepilot" / "bin"
    fake_bin_dir.mkdir(parents=True)
    fake_python = fake_bin_dir / "python"
    fake_python.touch()

    shim = tmp_path / "spacepilot"
    shim.write_text(
        "#!/bin/sh\n"
        f"'''exec' '{fake_python}' \"$0\" \"$@\"\n"
        "' '''\n"
    )
    shim.chmod(0o755)

    resolved = rt._spacepilot_console_python(which_fn=lambda name: str(shim))
    assert resolved == str(fake_python)


def test_spacepilot_console_python_returns_none_when_spacepilot_is_not_on_path():
    from spacepilot import runtimes as rt

    assert rt._spacepilot_console_python(which_fn=lambda name: None) is None


def test_interpreter_prefers_the_console_script_over_ambient_sys_executable(monkeypatch, tmp_path):
    """The whole point: two different callers -- one that happens to *be*
    the pipx venv's own interpreter, one that is not -- must resolve to the
    identical interpreter path for a shared-interpreter runtime."""
    from spacepilot import runtimes as rt

    monkeypatch.delenv("SPACEPILOT_PYTHON", raising=False)
    monkeypatch.delenv("PLUTO_PYTHON", raising=False)
    monkeypatch.setattr(rt, "_spacepilot_console_python", lambda which_fn=None: "/fake/pipx/venvs/spacepilot/bin/python")
    assert rt.interpreter() == "/fake/pipx/venvs/spacepilot/bin/python"
    # sys.executable of *this* test process is almost certainly a different
    # path (miniconda/pytest venv, not a pipx spacepilot venv) -- proving
    # interpreter() no longer falls back to it when a console script exists.
    assert rt.interpreter() != sys.executable


def test_interpreter_falls_back_to_sys_executable_when_no_console_script_is_found(monkeypatch):
    from spacepilot import runtimes as rt

    monkeypatch.delenv("SPACEPILOT_PYTHON", raising=False)
    monkeypatch.delenv("PLUTO_PYTHON", raising=False)
    monkeypatch.setattr(rt, "_spacepilot_console_python", lambda which_fn=None: None)
    assert rt.interpreter() == sys.executable


def test_interpreter_explicit_env_override_still_wins(monkeypatch):
    from spacepilot import runtimes as rt

    monkeypatch.setenv("SPACEPILOT_PYTHON", "/explicit/override/python")
    monkeypatch.setattr(rt, "_spacepilot_console_python", lambda which_fn=None: "/fake/pipx/python")
    assert rt.interpreter() == "/explicit/override/python"
