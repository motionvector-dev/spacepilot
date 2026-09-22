"""The suite must never write the developer's real config file.

`.spacepilot_config.json` is machine-local, mode 0600, and carries provider
credentials. A suite run used to POST /api/cockpit/config at the real path and
leave fixture values behind — `aws_profile: "new-profile"` then broke every AWS
path on that machine. Same lesson `conftest.py` already learned for the outputs
directory, one file over.

These assert against wherever the config would really live, not against one
hardcoded path: the checkout when running from one, the per-user data directory
otherwise. A change to that resolution must not quietly disarm the guard.
"""

import json
import os
from pathlib import Path

from spacepilot import cli

CONFIG_NAMES = (".spacepilot_config.json", ".pluto_config.json")


def _real_roots():
    """Every directory a real config could resolve to on this machine."""
    roots = {Path(__file__).resolve().parent.parent}  # the checkout
    try:
        from spacepilot import paths

        for fn in ("checkout_root", "user_data_dir", "state_root"):
            get = getattr(paths, fn, None)
            if get is None:
                continue
            try:
                root = get()
            except Exception:
                continue
            if root:
                roots.add(Path(root).resolve())
    except ImportError:  # pragma: no cover - paths always imports today
        pass
    return roots


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
    for root in _real_roots():
        token_file = root / ".studio_token"
        if root == Path(__file__).resolve().parent.parent:
            assert not token_file.exists(), "the suite minted .studio_token in the checkout"
