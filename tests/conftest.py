"""Shared test setup.

Point the API at a throwaway outputs directory before spacepilot.web_api is
imported. Without this the suite writes generated clips into the real
asset library and every run leaves more junk behind.

Same for the record store: `spacepilot measure` writes to $SPACEPILOT_DATA_DIR when
it is set, and to the repo's registry otherwise. Unset, a suite that records
anything would commit-block the checkout it ran in.

Same again for `.spacepilot_config.json`, and for worse reasons: it is
machine-local, mode 0600, and carries provider credentials. Unredirected, the
cockpit-config test POSTed fixture values over the developer's real file —
`aws_profile: "new-profile"` then broke every AWS path on that machine. The
studio token follows, so importing the settings never mints `.studio_token`
into the checkout either.
"""

import os
import secrets
import tempfile
from pathlib import Path

import pytest

_TMP_OUTPUTS = Path(tempfile.mkdtemp(prefix="pluto-test-outputs-"))
os.environ["PLUTO_OUTPUTS_DIR"] = str(_TMP_OUTPUTS)

_TMP_DATA = Path(tempfile.mkdtemp(prefix="pluto-test-data-"))
os.environ["SPACEPILOT_DATA_DIR"] = str(_TMP_DATA)

_TMP_CONFIG_DIR = Path(tempfile.mkdtemp(prefix="spacepilot-test-config-"))
os.environ["SPACEPILOT_CONFIG_FILE"] = str(_TMP_CONFIG_DIR / ".spacepilot_config.json")

os.environ.setdefault("SPACEPILOT_STUDIO_TOKEN", secrets.token_hex(32))

# A system id that can never collide with a real, shipped one (those are
# always a slugified "<chip>-<memory>gb", e.g. "apple-m1-max-32gb" — see
# spacepilot.measurements.system_id_for). A test that needs a System for a
# Measurement record should build it from this id instead of inventing a
# real-looking one.
FAKE_SYSTEM_ID = "spacepilot-test-fixture"


@pytest.fixture
def fake_system():
    from spacepilot.measurements import System
    return System(id=FAKE_SYSTEM_ID, backend="cpu", os_name="test")


def _shipped_system_ids() -> set[str]:
    from spacepilot.measurements import SHIPPED_SYSTEMS_DIR
    if not SHIPPED_SYSTEMS_DIR.exists():
        return set()
    return {p.stem for p in SHIPPED_SYSTEMS_DIR.glob("*.yaml")}


def shipped_id_collisions() -> list[str]:
    """Entries in the *default* (SPACEPILOT_DATA_DIR-redirected) measurement
    store that share an id with something already shipped in the repo.

    `load_measurements`/`load_systems` merge the shipped corpus with this
    store, and for systems "a locally rewritten record wins on id" — so a
    test that records under a real machine's id (by writing through the
    default store rather than an explicit `root=` or a fully isolated
    `MEASUREMENTS_DIR`/`SYSTEMS_DIR`) silently overwrites or blends into
    that real system's data. That is exactly what would make
    test_exported_json_matches_the_registry's regenerated web/registry.json
    stop matching what shipped, on some test run far away from this one.
    Returns the offending ids so the test that caused it is identifiable.
    """
    from spacepilot.measurements import MEASUREMENTS_DIR, SYSTEMS_DIR

    shipped = _shipped_system_ids()
    if not shipped:
        return []
    offenders: set[str] = set()
    if MEASUREMENTS_DIR.exists():
        offenders |= {p.name for p in MEASUREMENTS_DIR.iterdir() if p.is_dir()} & shipped
    if SYSTEMS_DIR.exists():
        offenders |= {p.stem for p in SYSTEMS_DIR.glob("*.yaml")} & shipped
    return sorted(offenders)


@pytest.fixture(autouse=True)
def _no_shipped_system_id_pollution():
    """Fail the test that does it, not test_exported_json_matches_the_registry
    three tests later. See `shipped_id_collisions` for the mechanism."""
    yield
    offenders = shipped_id_collisions()
    assert not offenders, (
        f"this test wrote to the default measurement/system store under "
        f"real/shipped system id(s) {offenders} — use an explicit root=tmp_path, "
        f"the `fake_system` fixture / FAKE_SYSTEM_ID, or monkeypatch "
        f"ms.MEASUREMENTS_DIR/ms.SYSTEMS_DIR, so it cannot poison "
        f"test_exported_json_matches_the_registry"
    )
