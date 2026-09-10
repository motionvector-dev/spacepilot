"""The "isolated" install flag: a pip runtime whose own pins would fight this
project's shared interpreter, so it gets its own venv instead.

edge0 (spacepilot/registry/runtimes/edge0.yaml) is the first of these -- it
pins `mlx-lm==0.31.0` exactly, which would downgrade this registry's own
`mlx-lm>=0.31.3` runtime if both were installed into the same interpreter.
These tests exercise the mechanism against a synthetic runtime and a fake
venv so they never touch the network or create a real environment.
"""

import stat
import sys

import pytest

from spacepilot.runtimes import Install, Runtime, parse_runtime


def _isolated_runtime(**overrides) -> Runtime:
    base = dict(
        id="fake-isolated", name="Fake Isolated", summary="A synthetic isolated runtime.",
        homepage=None, serves=["text"], backends=["metal"], license="Apache-2.0",
        install=Install(method="pip", package="fakeiso", isolated=True, checked="2026-09-10"),
        verify_import="fakeiso",
    )
    base.update(overrides)
    return Runtime(**base)


def test_parse_runtime_reads_isolated_flag_from_install():
    raw = {
        "schema": 1, "id": "fake-isolated", "name": "Fake Isolated", "summary": "s",
        "license": "Apache-2.0", "serves": ["text"], "backends": ["metal"],
        "install": {"method": "pip", "package": "fakeiso", "isolated": True},
        "verify": {"import": "fakeiso"},
    }
    r = parse_runtime(raw, "fake.yaml")
    assert r.install.isolated is True


def test_isolated_defaults_to_false_when_absent():
    raw = {
        "schema": 1, "id": "x", "name": "X", "summary": "s", "license": "MIT",
        "serves": ["image"], "backends": ["cpu"],
        "install": {"method": "pip", "package": "x"}, "verify": {"import": "x"},
    }
    r = parse_runtime(raw, "x.yaml")
    assert r.install.isolated is False


def test_edge0_recipe_is_isolated():
    """edge0 pins mlx-lm==0.31.0 exactly; installing it into the shared
    interpreter downgrades this registry's own mlx-lm>=0.31.3 runtime."""
    from spacepilot.runtimes import runtimes
    edge0 = runtimes()["edge0"]
    assert edge0.install.isolated is True
    assert edge0.install.source and "edge0.git@" in edge0.install.source


def test_isolated_env_dir_is_keyed_by_runtime_id(monkeypatch, tmp_path):
    from spacepilot import runtimes as rt
    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path))
    r = _isolated_runtime()
    assert rt.isolated_env_dir(r) == tmp_path / "fake-isolated"
    assert rt.isolated_python(r) == tmp_path / "fake-isolated" / "bin" / "python"
    assert rt.isolated_bin(r) == tmp_path / "fake-isolated" / "bin" / "fakeiso"


def test_check_reports_not_installed_when_no_venv_exists_yet(monkeypatch, tmp_path):
    from spacepilot import runtimes as rt
    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path))
    r = _isolated_runtime()

    st = rt.check(r)
    assert not st.installed
    assert st.external
    assert "spacepilot runtimes install fake-isolated" in st.reason


def test_check_finds_a_runtime_installed_in_its_isolated_venv(monkeypatch, tmp_path):
    """A real venv layout with a fake python that reports a version, standing
    in for the isolated env the way test_runtimes.py's mflux test stands a
    fake bin dir in for a conda env."""
    from spacepilot import runtimes as rt
    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path))
    r = _isolated_runtime()

    env_bin = tmp_path / "fake-isolated" / "bin"
    env_bin.mkdir(parents=True)
    fake_py = env_bin / "python"
    fake_py.write_text(
        "#!/bin/sh\n"
        'echo "9.9.9"\n'
    )
    fake_py.chmod(fake_py.stat().st_mode | stat.S_IEXEC)

    st = rt.check(r)
    assert st.installed
    assert st.external
    assert st.external_path == str(fake_py)
    assert st.version == "9.9.9"


def test_install_command_targets_the_isolated_venvs_own_interpreter(monkeypatch, tmp_path):
    """`py=` is ignored for an isolated runtime -- it never installs into
    whatever interpreter the caller happens to name."""
    from spacepilot import runtimes as rt
    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path))
    r = _isolated_runtime()

    argv = rt.install_command(r, py="/tmp/some-other-python")
    assert argv[0] == str(tmp_path / "fake-isolated" / "bin" / "python")
    assert argv[1:4] == ["-m", "pip", "install"]
    assert argv[-1] == "fakeiso"


def test_edge0_install_command_uses_the_git_pinned_source(monkeypatch, tmp_path):
    from spacepilot import runtimes as rt
    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path))
    edge0 = rt.runtimes()["edge0"]

    argv = rt.install_command(edge0)
    assert argv[0] == str(tmp_path / "edge0" / "bin" / "python")
    assert argv[-1] == edge0.install.source
    assert argv[-1].endswith("@fbab5f8c08e843e204c0fc6ae18b89a154c652cf")


def test_preview_for_isolated_is_a_clean_no_op_not_an_error():
    """Same reasoning as the script method's preview: an isolated install
    never touches the shared interpreter, so there is nothing to diff."""
    from spacepilot import runtimes as rt
    r = _isolated_runtime()
    imp = rt.preview(r)
    assert imp.error is None
    assert not imp.new and not imp.upgrades and not imp.downgrades
    assert not imp.is_disruptive


def test_install_creates_the_venv_then_pip_installs_then_verifies(monkeypatch, tmp_path):
    """`install()` for an isolated runtime: create the venv if missing, pip
    install into it, then re-verify through the ordinary `check()` path --
    the install itself is never the evidence."""
    import subprocess as real_subprocess

    from spacepilot import runtimes as rt

    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path))
    r = _isolated_runtime()
    env_dir = tmp_path / "fake-isolated"
    fake_py = env_dir / "bin" / "python"

    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == [sys.executable, "-m", "venv"]:
            (env_dir / "bin").mkdir(parents=True)
            fake_py.write_text("#!/bin/sh\necho 1.0.0\n")
            fake_py.chmod(fake_py.stat().st_mode | stat.S_IEXEC)
            return real_subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[0] == str(fake_py) and "pip" in argv:
            return real_subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[0] == str(fake_py) and argv[1] == "-c":
            # the post-install `check()` version probe
            return real_subprocess.CompletedProcess(argv, 0, stdout="1.0.0\n", stderr="")
        return real_subprocess.CompletedProcess(argv, 1, stdout="", stderr="unexpected call")

    monkeypatch.setattr(rt.subprocess, "run", fake_run)

    st = rt.install(r)
    assert st.installed
    assert st.version == "1.0.0"
    assert st.external_path == str(fake_py)
    # venv creation happened before the pip install
    venv_call = next(c for c in calls if c[:3] == [sys.executable, "-m", "venv"])
    pip_call = next(c for c in calls if "pip" in c)
    assert calls.index(venv_call) < calls.index(pip_call)


def test_install_reuses_an_existing_venv_instead_of_recreating_it(monkeypatch, tmp_path):
    from spacepilot import runtimes as rt

    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path))
    r = _isolated_runtime()
    env_dir = tmp_path / "fake-isolated"
    (env_dir / "bin").mkdir(parents=True)
    fake_py = env_dir / "bin" / "python"
    fake_py.write_text("#!/bin/sh\necho 2.0.0\n")
    fake_py.chmod(fake_py.stat().st_mode | stat.S_IEXEC)

    import subprocess as real_subprocess
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        assert argv[:3] != [sys.executable, "-m", "venv"], "venv already existed, must not recreate"
        if argv[0] == str(fake_py) and argv[1] == "-c":
            return real_subprocess.CompletedProcess(argv, 0, stdout="2.0.0\n", stderr="")
        return real_subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(rt.subprocess, "run", fake_run)

    st = rt.install(r)
    assert st.installed
    assert st.version == "2.0.0"
