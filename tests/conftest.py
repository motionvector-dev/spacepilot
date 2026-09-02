"""Shared test setup.

Point the API at a throwaway outputs directory before spacepilot.web_api is
imported. Without this the suite writes generated clips into the real
asset library and every run leaves more junk behind.

Same for the record store: `spacepilot measure` writes to $SPACEPILOT_DATA_DIR when
it is set, and to the repo's registry otherwise. Unset, a suite that records
anything would commit-block the checkout it ran in.
"""

import os
import tempfile
from pathlib import Path

_TMP_OUTPUTS = Path(tempfile.mkdtemp(prefix="pluto-test-outputs-"))
os.environ["PLUTO_OUTPUTS_DIR"] = str(_TMP_OUTPUTS)

_TMP_DATA = Path(tempfile.mkdtemp(prefix="pluto-test-data-"))
os.environ["SPACEPILOT_DATA_DIR"] = str(_TMP_DATA)
