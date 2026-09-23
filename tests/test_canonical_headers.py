"""First-party browser clients must send the canonical compute-token header."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CLIENTS = (
    "spacepilot/web/app.js", "spacepilot/web/cockpit.js", "spacepilot/web/create.js", "spacepilot/web/docs.html", "spacepilot/web/sidebar.js",
    "spacepilot/web/onboard-v2.html", "spacepilot/web/onboard.html",
)


def test_first_party_clients_do_not_send_the_legacy_token_header():
    sources = {path: (ROOT / path).read_text() for path in CLIENTS}
    assert all("X-Pluto-Token" not in source for source in sources.values())
    assert all("X-SpacePilot-Token" in source for source in sources.values())
