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

_TMP_OUTPUTS = Path(tempfile.mkdtemp(prefix="pluto-test-outputs-"))
os.environ["PLUTO_OUTPUTS_DIR"] = str(_TMP_OUTPUTS)

_TMP_DATA = Path(tempfile.mkdtemp(prefix="pluto-test-data-"))
os.environ["SPACEPILOT_DATA_DIR"] = str(_TMP_DATA)

_TMP_CONFIG_DIR = Path(tempfile.mkdtemp(prefix="spacepilot-test-config-"))
os.environ["SPACEPILOT_CONFIG_FILE"] = str(_TMP_CONFIG_DIR / ".spacepilot_config.json")

os.environ.setdefault("SPACEPILOT_STUDIO_TOKEN", secrets.token_hex(32))
