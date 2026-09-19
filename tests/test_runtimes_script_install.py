"""The "script" install method: a runtime with no Python package at all,
verified by shelling out to its own binary rather than importing anything.

Desert Ant CLI (Swift, released as a signed tarball) is the first of these --
see spacepilot/registry/runtimes/desert-ant.yaml. These tests exercise the
method against a synthetic runtime so they do not depend on the real binary
being on the test machine's PATH.
"""

import os
import stat

import pytest

from spacepilot.runtimes import (
    Install, Runtime, RuntimeError_, parse_runtime,
)


def _script_runtime(**overrides) -> Runtime:
    base = dict(
        id="fake-cli", name="Fake CLI", summary="A synthetic script runtime.",
        homepage=None, serves=["audio"], backends=["cpu"], license="MIT",
        install=Install(method="script", package="fakecli",
                         script_url="https://example.invalid/install.sh@deadbeef",
                         checked="2026-09-10"),
        verify_binary="fakecli",
    )
    base.update(overrides)
    return Runtime(**base)


def test_parse_runtime_accepts_script_method_with_script_url_and_binary():
    raw = {
        "schema": 1, "id": "fake-cli", "name": "Fake CLI", "summary": "s",
        "license": "MIT", "serves": ["audio"], "backends": ["cpu"],
        "install": {"method": "script", "package": "fakecli",
                    "script_url": "https://example.invalid/install.sh"},
        "verify": {"binary": "fakecli"},
    }
    r = parse_runtime(raw, "fake.yaml")
    assert r.install.method == "script"
    assert r.install.script_url == "https://example.invalid/install.sh"
    assert r.verify_binary == "fakecli"
    assert r.verify_import is None


def test_parse_runtime_rejects_script_method_missing_script_url():
    raw = {
        "schema": 1, "id": "fake-cli", "name": "Fake CLI", "summary": "s",
        "license": "MIT", "serves": ["audio"], "backends": ["cpu"],
        "install": {"method": "script", "package": "fakecli"},
        "verify": {"binary": "fakecli"},
    }
    with pytest.raises(RuntimeError_, match="script_url"):
        parse_runtime(raw, "fake.yaml")


def test_parse_runtime_rejects_script_method_missing_verify_binary():
    raw = {
        "schema": 1, "id": "fake-cli", "name": "Fake CLI", "summary": "s",
        "license": "MIT", "serves": ["audio"], "backends": ["cpu"],
        "install": {"method": "script", "package": "fakecli",
                    "script_url": "https://example.invalid/install.sh"},
        "verify": {},
    }
    with pytest.raises(RuntimeError_, match="binary"):
        parse_runtime(raw, "fake.yaml")


def test_check_script_reports_installed_when_the_binary_resolves(tmp_path, monkeypatch):
    from spacepilot import runtimes as rt

    r = _script_runtime()
    exe = tmp_path / "fakecli"
    exe.write_text("#!/bin/sh\necho fakecli 1.2.3\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("SPACEPILOT_FAKE_CLI_BIN", str(exe))

    st = rt.check(r)
    assert st.installed
    assert st.external
    assert st.external_path == str(exe)
    assert st.version == "fakecli 1.2.3"


def test_check_script_reports_a_reason_when_the_binary_is_absent(monkeypatch):
    from spacepilot import runtimes as rt

    r = _script_runtime()
    monkeypatch.delenv("SPACEPILOT_FAKE_CLI_BIN", raising=False)

    st = rt.check(r)
    # No override env, and `which` almost certainly does not resolve a
    # fictitious binary named "fakecli" on the test machine.
    if st.installed:
        pytest.skip("a real 'fakecli' happens to be on this machine's PATH")
    assert not st.installed
    assert st.reason
    assert "fakecli" in st.reason


def test_install_command_for_script_method_names_the_pinned_url():
    from spacepilot import runtimes as rt

    r = _script_runtime()
    argv = rt.install_command(r)
    assert argv[0] == "sh"
    assert argv[1] == "-c"
    assert r.install.script_url in argv[2]
    assert argv[2].startswith("curl -fsSL")


def test_preview_for_script_method_is_a_clean_no_op_not_an_error():
    """The CLI's `runtimes install` treats a non-empty `imp.error` as fatal,
    so a script install must report "nothing to resolve" rather than error
    out of an install path that was never going to touch pip at all."""
    from spacepilot import runtimes as rt

    r = _script_runtime()
    imp = rt.preview(r)
    assert imp.error is None
    assert not imp.new and not imp.upgrades and not imp.downgrades
    assert not imp.is_disruptive


def test_install_runs_the_script_then_verifies_by_check(tmp_path, monkeypatch):
    """`install()` shells out to the pinned script, then re-verifies through
    the ordinary `check()` path -- the install itself is not the evidence."""
    import subprocess as real_subprocess

    from spacepilot import runtimes as rt

    exe = tmp_path / "fakecli"
    real_run = real_subprocess.run

    def fake_run(argv, **kwargs):
        if argv[:2] == ["sh", "-c"]:
            # Simulate the pinned install script placing the binary; do not
            # actually touch the network.
            exe.write_text("#!/bin/sh\necho fakecli 9.9.9\n")
            exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
            return real_subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        return real_run(argv, **kwargs)

    monkeypatch.setenv("SPACEPILOT_FAKE_CLI_BIN", str(exe))
    monkeypatch.setattr(rt.subprocess, "run", fake_run)

    r = _script_runtime()
    st = rt.install(r)
    assert st.installed
    assert st.version == "fakecli 9.9.9"
