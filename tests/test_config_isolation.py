"""The suite must never write the developer's real config file.

`.spacepilot_config.json` is machine-local, mode 0600, and carries provider
credentials. A suite run used to POST /api/cockpit/config at the real path and
leave fixture values behind — `aws_profile: "new-profile"` then broke every AWS
path on that machine. Same lesson `conftest.py` already learned for the outputs
directory, one file over.

These assert against wherever the config would really live, not against one
hardcoded path. In practice that is the checkout, which is what a developer
runs the suite from and what the clobber actually hit. The per-user data
directory is checked too, for an installed copy — and it has to be asked for
with `$SPACEPILOT_DATA_DIR` cleared, because conftest points that at a tmp dir
and an unclearing check would compare one tmp path against another and pass
regardless.
"""

import json
import os
from pathlib import Path

from spacepilot import cli, paths

CONFIG_NAMES = (".spacepilot_config.json", ".pluto_config.json")
CHECKOUT = Path(__file__).resolve().parent.parent
DATA_DIR_ENV_NAMES = ("SPACEPILOT_DATA_DIR", "PLUTO_DATA_DIR")


def _true_user_data_dir():
    """The real per-user root, not the one conftest redirected."""
    saved = {k: os.environ.pop(k, None) for k in DATA_DIR_ENV_NAMES}
    try:
        return paths.user_data_dir()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def _real_roots():
    """Every directory a real config could resolve to on this machine."""
    roots = {CHECKOUT, _true_user_data_dir()}
    checkout = paths.checkout_root()
    if checkout:
        roots.add(Path(checkout).resolve())
    return {Path(r).resolve() for r in roots}


def _real_config_paths():
    return [root / name for root in _real_roots() for name in CONFIG_NAMES]


def _fingerprint(path: Path):
    if not path.exists():
        return None
    return (path.stat().st_mtime_ns, path.read_bytes())


def _snapshot():
    return {p: _fingerprint(p) for p in _real_config_paths()}


def test_the_config_path_is_redirected_away_from_every_real_root():
    """conftest points CONFIG_FILE at a throwaway file before cli is imported."""
    live = {cli.CONFIG_FILE.resolve(), cli.LEGACY_CONFIG_FILE.resolve()}
    real = {p.resolve() for p in _real_config_paths()}
    assert not (live & real), f"the suite is pointed at a real config: {live & real}"
    assert cli.CONFIG_FILE == Path(os.environ["SPACEPILOT_CONFIG_FILE"])


def test_saving_a_config_leaves_every_real_config_untouched():
    before = _snapshot()
    cli.save_config({**cli.DEFAULT_CONFIG, "aws_profile": "test-only-profile"})
    assert _snapshot() == before, "save_config wrote a real config file"
    assert json.loads(cli.CONFIG_FILE.read_text())["aws_profile"] == "test-only-profile"


def test_the_cockpit_config_route_writes_only_the_redirected_file():
    """The route that started this: it calls save_config on the real path."""
    from fastapi.testclient import TestClient
    from spacepilot.web_api import app, STUDIO_TOKEN

    client = TestClient(app)
    before = _snapshot()
    r = client.post(
        "/api/cockpit/config",
        json={"config": {"aws_profile": "route-test-profile"}},
        headers={"X-Pluto-Token": STUDIO_TOKEN},
    )
    assert r.status_code == 200
    assert _snapshot() == before, "POST /api/cockpit/config wrote a real config file"
    assert cli.load_config()["aws_profile"] == "route-test-profile"


def test_importing_the_settings_does_not_mint_a_token_into_the_checkout():
    """`.studio_token` is written on first settings access; not during a run."""
    from spacepilot.core.config import get_settings

    assert get_settings().studio_token == os.environ["SPACEPILOT_STUDIO_TOKEN"]
    assert not (CHECKOUT / ".studio_token").exists(), (
        "the suite minted .studio_token into the checkout"
    )


def test_an_empty_override_falls_back_instead_of_becoming_a_directory():
    """`Path("")` is `Path(".")`, which would make CONFIG_FILE a directory.

    `save_config` then fails on os.replace. paths.py strips and falls back
    everywhere for this reason; the override has to do the same.

    Run in a subprocess, deliberately. Reloading `spacepilot.cli` in-process
    would point the live module at the real config for the length of the
    test, and this suite runs background threads — a guard test must not open
    the very window it exists to close.
    """
    import subprocess
    import sys

    env = {**os.environ, "SPACEPILOT_CONFIG_FILE": "   ", "PYTHONPATH": str(CHECKOUT)}
    proc = subprocess.run(
        [sys.executable, "-c",
         "from spacepilot import cli; print(cli.CONFIG_FILE); print(cli.LEGACY_CONFIG_FILE)"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    config_file, legacy_file = (Path(p) for p in proc.stdout.strip().splitlines())

    assert config_file.name == ".spacepilot_config.json"
    assert config_file != Path(".") and not config_file.is_dir()
    assert legacy_file.name == ".pluto_config.json"
