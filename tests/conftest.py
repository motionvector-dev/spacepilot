"""Shared test setup.

Point the API at a throwaway outputs directory before spacepilot.web_api is
imported. Without this the suite writes generated clips into the real
asset library and every run leaves more junk behind.
"""

import os
import tempfile
from pathlib import Path

_TMP_OUTPUTS = Path(tempfile.mkdtemp(prefix="pluto-test-outputs-"))
os.environ["PLUTO_OUTPUTS_DIR"] = str(_TMP_OUTPUTS)
