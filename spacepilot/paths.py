"""Where registry data is read from, and where new records are written.

Those are two different questions and the old code answered both with
`Path(__file__).parents[2]`, which is the repo root in a checkout and
`site-packages/` in an install. So a released wheel looked for its catalogue in
a directory that did not exist, and `pluto measure` wrote records into
site-packages, where they are invisible, unbackuped, and destroyed by the next
`pip install --upgrade`.

The split follows what the data is.

**The catalogue ships.** `registry/models` and `registry/runtimes` are curated
content, versioned with the release, never written at runtime. They live inside
the package and are found with `importlib.resources`, not `__file__`
arithmetic — the package knows where it is, the filesystem layout around it
does not.

**The corpus is written.** `registry/measurements`, `registry/systems` and
sweep runs are produced by the machine that runs them. Writes go to a user data
directory; reads merge what shipped with what the user has recorded, so a fresh
install still sees the records that came with it and a long-lived one sees
both.

**A checkout is the exception, on purpose.** The corpus is also a git tree that
people contribute to by opening a PR. If a contributor's `pluto measure` wrote
into `~/Library/Application Support/` there would be nothing to commit, and the
corpus would stop growing. So inside a checkout the writable root is the repo's
own `spacepilot/registry/`, exactly as before.

`$SPACEPILOT_DATA_DIR` overrides all of it, including the checkout rule — that
is what lets the test suite redirect writes the way `$PLUTO_OUTPUTS_DIR`
already does for generated files.
"""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path
from typing import List

APP_NAME = "spacepilot"
DATA_DIR_ENV = "SPACEPILOT_DATA_DIR"


def env_value(name: str, *legacy_names: str, default: str | None = None) -> str | None:
    """Read a canonical environment variable with backwards-compatible aliases.

    New configuration uses the ``SPACEPILOT_`` namespace.  The old ``PLUTO_``
    names remain valid, but a canonical value wins when both are present.  A
    small helper keeps that precedence identical across the CLI, API and
    drivers instead of leaving each caller to implement its own fallback.
    Empty strings are values too: callers that need a non-empty setting should
    apply ``.strip()`` or their existing validation after reading it.
    """
    for key in (name, *legacy_names):
        value = os.environ.get(key)
        if value is not None:
            return value
    return default


def shipped_registry_root() -> Path:
    """The read-only catalogue that travels inside the wheel.

    `resources.files` rather than `__file__` because it is the package's own
    answer to "where am I", and it stays right when the package is installed,
    zipped, or vendored somewhere this module cannot guess.
    """
    return Path(str(resources.files(APP_NAME))) / "registry"


def checkout_root() -> Path | None:
    """The repo root when running from a source checkout, otherwise None.

    Same walk `spacepilot.pluto.core.config` uses. `pyproject.toml` beside a
    `spacepilot/` directory is what a checkout has and an installed package
    does not: `site-packages/` holds the package but never the project file.
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").is_file() and (current / APP_NAME).is_dir():
            return current
        current = current.parent
    return None


def user_data_dir() -> Path:
    """Platform user-data location, or `$SPACEPILOT_DATA_DIR` when set."""
    override = env_value(DATA_DIR_ENV, "PLUTO_DATA_DIR", default="").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / APP_NAME).resolve()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (base / APP_NAME).resolve()


def writable_registry_root() -> Path:
    """Where new records go. Never inside site-packages."""
    if env_value(DATA_DIR_ENV, "PLUTO_DATA_DIR", default="").strip():
        return user_data_dir() / "registry"
    root = checkout_root()
    if root is not None:
        return root / APP_NAME / "registry"
    return user_data_dir() / "registry"


def shipped_dir(name: str) -> Path:
    return shipped_registry_root() / name


def writable_dir(name: str) -> Path:
    return writable_registry_root() / name


def read_roots(name: str) -> List[Path]:
    """Every directory a reader should merge, shipped first, user last.

    Deduplicated by resolved path, because in a checkout the two are the same
    directory and reading it twice would double every record.
    """
    out: List[Path] = []
    for candidate in (shipped_dir(name), writable_dir(name)):
        resolved = candidate.resolve()
        if resolved not in out:
            out.append(resolved)
    return out
