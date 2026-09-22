"""mlx-lm installs into its own venv, and still serves from there.

Resolving mlx-lm into the shared interpreter downgrades `tokenizers` 0.23.2 ->
0.22.2 (measured 2026-09-22 against the released v2.8.0 tool venv), so the
installer correctly refuses by default -- and the released binary could then
serve none of the three models that carry a route. An isolated venv removes
the conflict instead of asking for the downgrade.

Installing there is only half of it. Both drivers run their work as a
subprocess of `python_bin`, and `python_bin` used to be this project's shared
interpreter, which would not have mlx-lm at all after an isolated install. And
the isolated venv has no `spacepilot` package in it, so `-m
spacepilot.drivers.mlx_lm_runner` cannot resolve there either. These tests pin
both halves: the install goes to its own environment, and serving follows it.
"""

import subprocess
import sys

import pytest

from spacepilot import runtimes as rt
from spacepilot.runtimes import runtimes


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """A real venv standing in for the one `runtimes install mlx-lm` makes."""
    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path / "runtime-envs"))
    env_dir = rt.isolated_env_dir(runtimes()["mlx-lm"])
    env_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "venv", str(env_dir)],
                   capture_output=True, text=True, check=True)
    return env_dir


def test_mlx_lm_installs_into_its_own_environment():
    r = runtimes()["mlx-lm"]
    assert r.install.isolated is True
    argv = rt.install_command(r)
    assert argv[0] == str(rt.isolated_python(r))
    assert argv[0] != rt.interpreter()


def test_an_isolated_install_cannot_downgrade_the_shared_environment():
    """The whole point: nothing in the user's own interpreter moves."""
    imp = rt.preview(runtimes()["mlx-lm"])
    assert imp.downgrades == []
    assert imp.blocked is False
    assert imp.is_disruptive is False


def test_the_isolated_venv_has_no_spacepilot_package(isolated_env):
    """Why the runner cannot be launched with `-m spacepilot...` from there."""
    py = rt.isolated_python(runtimes()["mlx-lm"])
    proc = subprocess.run([str(py), "-c", "import spacepilot"],
                          capture_output=True, text=True, cwd=str(isolated_env.parent))
    assert proc.returncode != 0, "this venv sees spacepilot; the premise is wrong"


def test_the_drivers_look_for_mlx_lm_where_it_was_installed(isolated_env):
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver
    from spacepilot.drivers.mlx_embed_driver import MlxEmbedDriver

    want = str(rt.isolated_python(runtimes()["mlx-lm"]))
    assert MlxLmDriver().python_bin == want
    assert MlxEmbedDriver().python_bin == want


def test_without_an_isolated_venv_the_shared_interpreter_still_serves(tmp_path, monkeypatch):
    """An existing install in someone's own environment keeps working."""
    monkeypatch.setenv("SPACEPILOT_RUNTIME_ENVS_DIR", str(tmp_path / "none"))
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    assert MlxLmDriver().python_bin == rt.interpreter()


def test_the_runner_is_launched_by_path_not_as_a_package_module(isolated_env):
    from spacepilot.drivers import mlx_lm_runner
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    cmd = MlxLmDriver()._command("/snap", "/out.json", 16, 512, 0.0, False)
    assert "-m" not in cmd
    assert mlx_lm_runner.__file__ in cmd


def test_the_embedding_runner_is_launched_by_path_too(isolated_env, monkeypatch):
    from spacepilot.drivers import mlx_embed_runner
    from spacepilot.drivers.mlx_embed_driver import MlxEmbedDriver

    seen = {}

    def spy(cmd, *a, **kw):
        seen["cmd"] = cmd
        raise subprocess.TimeoutExpired(cmd, 1)

    driver = MlxEmbedDriver()
    monkeypatch.setattr(driver, "asset_dir", lambda v=None: ("/snap", "abc123"))
    monkeypatch.setattr(subprocess, "run", spy)
    with pytest.raises(Exception):
        driver.infer(["hello"], out_path="/tmp/out.json", max_tokens=8)

    assert "-m" not in seen["cmd"]
    assert mlx_embed_runner.__file__ in seen["cmd"]


def test_counting_prompt_tokens_never_imports_mlx_lm_into_this_process(isolated_env, monkeypatch):
    """The server process does not have mlx-lm any more; the venv does."""
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    seen = {}

    class Done:
        returncode = 0
        stdout = "7"
        stderr = ""

    def spy(cmd, *a, **kw):
        seen["cmd"] = cmd
        return Done()

    driver = MlxLmDriver()
    monkeypatch.setattr(driver, "asset_dir", lambda v=None: ("/snap", "abc123"))
    monkeypatch.setattr(subprocess, "run", spy)
    monkeypatch.setitem(sys.modules, "mlx_lm", None)  # an in-process import now fails

    assert driver.count_prompt_tokens([{"role": "user", "content": "hi"}]) == 7
    assert seen["cmd"][0] == driver.python_bin


def test_the_preview_payload_names_the_environment_it_would_install_into(isolated_env):
    """An agent reading `interpreter` must not be pointed at the daemon's."""
    from spacepilot import mcp_server

    out = mcp_server.spacepilot_preview_runtime_install("mlx-lm")
    assert out["isolated"] is True
    assert out["interpreter"] == str(rt.isolated_python(runtimes()["mlx-lm"]))
    assert out["blocked"] is False
