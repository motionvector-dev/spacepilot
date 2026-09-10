"""Where registry data is read from, and where new records are written.

Those are two different questions and the old code answered both with
`Path(__file__).parents[2]`, which is the repo root in a checkout and
`site-packages/` in an install. So a released wheel looked for its catalogue in
a directory that did not exist, and `spacepilot measure` wrote records into
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
people contribute to by opening a PR. If a contributor's `spacepilot measure` wrote
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
from dataclasses import dataclass
from fnmatch import fnmatch
from importlib import resources
from pathlib import Path
from typing import List, Sequence

APP_NAME = "spacepilot"
DATA_DIR_ENV = "SPACEPILOT_DATA_DIR"
MODELS_DIR_ENV = "SPACEPILOT_MODELS_DIR"
DAEMON_RUNTIME_DIR_ENV = "SPACEPILOT_DAEMON_RUNTIME_DIR"

# The identity is deliberately kept separate from the writable registry.  In
# particular, ``writable_registry_root`` may point into a checkout for
# contributors, while a machine's signing key must never move with a clone or
# get committed by accident.
IDENTITY_DIR_NAME = "identity"
IDENTITY_FILENAME = "identity.json"
IDENTITY_LOCK_FILENAME = ".identity.lock"


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

    Same walk `spacepilot.core.config` uses. `pyproject.toml` beside a
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


def legacy_user_data_dir() -> Path:
    """Pre-rename per-user data root; read-only compatibility location."""
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "pluto").resolve()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (base / "pluto").resolve()


def user_data_read_dirs() -> List[Path]:
    """Canonical then legacy data roots, without redirecting new writes."""
    canonical = user_data_dir()
    candidates = [canonical]
    # An explicit data-dir setting is already a compatibility decision and
    # must not silently mix unrelated data from the platform defaults.
    if not env_value(DATA_DIR_ENV, "PLUTO_DATA_DIR", default="").strip():
        candidates.append(legacy_user_data_dir())
    out: List[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in out:
            out.append(resolved)
    return out


RUNTIME_ENVS_DIR_ENV = "SPACEPILOT_RUNTIME_ENVS_DIR"


def runtime_envs_root() -> Path:
    """Root for SpacePilot-managed isolated runtime environments.

    A runtime whose own pins would fight this project's shared interpreter
    (edge0 pins `mlx-lm==0.31.0` exactly; this project's own `mlx-lm` recipe
    asks for `>=0.31.3`) gets its own venv here instead, one directory per
    runtime id, created by `spacepilot runtimes install <id>` -- see
    `Install.isolated` in `spacepilot/runtimes.py`. Lives under
    `user_data_dir()`, not the checkout: a venv is a machine-local build
    artifact, never something to commit or ship.
    """
    override = env_value(RUNTIME_ENVS_DIR_ENV, default="").strip()
    if override:
        return Path(override).expanduser().resolve()
    return user_data_dir() / "runtime-envs"


def runtime_env_dir(runtime_id: str) -> Path:
    """Where one runtime's isolated environment lives."""
    return runtime_envs_root() / runtime_id


def user_cache_dir() -> Path:
    """Canonical per-user cache root for SpacePilot-owned transient data."""
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return (Path(xdg).expanduser() / APP_NAME).resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Caches" / APP_NAME).resolve()
    return (Path.home() / ".cache" / APP_NAME).resolve()


def legacy_user_cache_dir() -> Path:
    """The former direct ``~/.cache/pluto`` root, for reads only."""
    return (Path.home() / ".cache" / "pluto").resolve()


def model_recommender_cache_dir() -> Path:
    """Canonical flat cache used by the legacy recommender compatibility API."""
    return user_cache_dir() / "models"


def model_recommender_cache_read_dirs() -> List[Path]:
    """Canonical recommender cache followed by its old read-only location."""
    out: List[Path] = []
    for candidate in (
        model_recommender_cache_dir(), legacy_user_cache_dir() / "models",
    ):
        resolved = candidate.resolve()
        if resolved not in out:
            out.append(resolved)
    return out


def identity_dir() -> Path:
    """The per-user directory containing this machine's signing identity.

    This always derives from :func:`user_data_dir`; unlike registry writes it
    never follows the checkout exception.  The identity module creates and
    validates the directory's restrictive permissions.
    """
    return user_data_dir() / IDENTITY_DIR_NAME


def identity_path() -> Path:
    """Path to the persistent (private) identity record."""
    return identity_dir() / IDENTITY_FILENAME


def identity_private_key_path() -> Path:
    """Descriptive alias for :func:`identity_path`."""
    return identity_path()


def identity_lock_path() -> Path:
    """Path used to serialize first identity creation."""
    return identity_dir() / IDENTITY_LOCK_FILENAME


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


def outputs_dir() -> Path:
    """Where generated artifacts go for CLI and transport-neutral services."""
    override = env_value("SPACEPILOT_OUTPUTS_DIR", "PLUTO_OUTPUTS_DIR", default="").strip()
    if override:
        return Path(override).expanduser().resolve()
    root = checkout_root()
    if root is not None:
        return (root / "outputs").resolve()
    return (user_data_dir() / "outputs").resolve()


def daemon_state_dir() -> Path:
    """Private, persistent state for the local daemon.

    This is deliberately separate from identity material.  Identity owns its
    keys; lifecycle owns transient sockets, logs and supervisor definitions.
    """
    return (user_data_dir() / "daemon").resolve()


def fleet_state_dir() -> Path:
    """Durable signed fleet control state, separate from daemon lifecycle."""
    return (user_data_dir() / "fleet").resolve()


def fleet_orders_path() -> Path:
    """The single durable, signed ORDERS manifest for this user."""
    return fleet_state_dir() / "fleet.yaml"


def daemon_log_dir() -> Path:
    """Where a user supervisor can write daemon stdout and stderr."""
    return (daemon_state_dir() / "logs").resolve()


def daemon_log_store_dir() -> Path:
    """The immutable LOG gossip store, separate from supervisor stdout logs."""
    return (daemon_state_dir() / "log").resolve()


def daemon_log_replica_dir() -> Path:
    """Verified remote LOG replicas, grouped by original author."""
    return daemon_log_store_dir() / "replicas"


def daemon_log_state_path() -> Path:
    """Persistent local LOG epoch/sequence metadata."""
    return daemon_log_store_dir() / "state.json"


def daemon_index_dir() -> Path:
    """Directory containing the rebuildable fleet index."""
    return (daemon_state_dir() / "index").resolve()


def daemon_index_path() -> Path:
    """The derived SQLite index; never a checkout or registry file."""
    return daemon_index_dir() / "fleet.sqlite3"


# Short names are useful to transport-neutral services and make the boundary
# explicit without overloading ``daemon_log_dir`` (which is supervisor logs).
log_store_dir = daemon_log_store_dir
log_replica_dir = daemon_log_replica_dir
log_state_path = daemon_log_state_path
index_dir = daemon_index_dir
index_path = daemon_index_path


def daemon_runtime_dir() -> Path:
    """Directory for the daemon's Unix-domain socket.

    A systemd unit sets ``SPACEPILOT_DAEMON_RUNTIME_DIR`` to its protected
    RuntimeDirectory.  An interactive foreground daemon uses XDG's runtime
    directory when available and otherwise a private data-directory fallback.
    """
    override = env_value(DAEMON_RUNTIME_DIR_ENV, default="").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform != "darwin":
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
        if xdg_runtime:
            return (Path(xdg_runtime).expanduser() / APP_NAME).resolve()
    return (daemon_state_dir() / "run").resolve()


def daemon_socket_path() -> Path:
    """The local daemon's filesystem-permission-protected socket path."""
    return daemon_runtime_dir() / "daemon.sock"


def launch_agent_path() -> Path:
    """The per-user launchd definition, on macOS."""
    return (Path.home() / "Library" / "LaunchAgents" / "com.spacepilot.daemon.plist").resolve()


def systemd_user_unit_path() -> Path:
    """The per-user systemd definition, on Linux."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
    config_home = Path(xdg_config).expanduser() if xdg_config else Path.home() / ".config"
    return (config_home / "systemd" / "user" / "spacepilot-daemon.service").resolve()


def read_roots(name: str) -> List[Path]:
    """Every directory a reader should merge, shipped first, user last.

    Deduplicated by resolved path, because in a checkout the two are the same
    directory and reading it twice would double every record.
    """
    out: List[Path] = []
    legacy = [] if checkout_root() is not None else [
        root / "registry" / name for root in user_data_read_dirs()[1:]
        if (root / "registry" / name).is_dir()
    ]
    for candidate in (shipped_dir(name), *legacy, writable_dir(name)):
        resolved = candidate.resolve()
        if resolved not in out:
            out.append(resolved)
    return out


def weights_dir() -> Path:
    """The writable Hugging Face Hub cache used for model repositories.

    ``HF_HOME`` is the parent of the repository cache, not the repository
    cache itself.  Passing it directly as ``snapshot_download(cache_dir=...)``
    would create a second, non-standard cache beside ``HF_HOME/hub`` and lose
    the deduplication this helper exists to preserve.

    ``SPACEPILOT_MODELS_DIR`` retains its historical meaning: when set it is
    the cache directory containing ``models--org--repo`` entries directly.
    """
    override = env_value(MODELS_DIR_ENV, "PLUTO_MODELS_DIR", default="").strip()
    if override:
        return Path(override).expanduser().resolve()

    hub_override = os.environ.get("HF_HUB_CACHE", "").strip()
    if not hub_override:
        hub_override = os.environ.get("HUGGINGFACE_HUB_CACHE", "").strip()
    if hub_override:
        return Path(hub_override).expanduser().resolve()

    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        return (Path(hf_home).expanduser() / "hub").resolve()

    xdg_cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    home = Path(xdg_cache).expanduser() if xdg_cache else Path.home() / ".cache"
    return (home / "huggingface" / "hub").resolve()


def legacy_weights_dir() -> Path:
    """The pre-resolver cache. Read-only fallback; never the new default."""
    return (Path.home() / ".spacepilot" / "models").resolve()


def weights_read_dirs() -> List[Path]:
    """Cache roots to inspect, in precedence order, without duplicates."""
    out: List[Path] = []
    for candidate in (weights_dir(), legacy_weights_dir()):
        if candidate not in out:
            out.append(candidate)
    return out


def revision_from_snapshot(path: Path | str | None) -> str | None:
    """Extract the commit from ``.../snapshots/<sha>`` without guessing."""
    if path is None:
        return None
    parts = Path(path).parts
    if "snapshots" not in parts:
        return None
    idx = len(parts) - 1 - parts[::-1].index("snapshots")
    return parts[idx + 1] if idx + 1 < len(parts) else None


@dataclass(frozen=True)
class ResolvedWeights:
    """Concrete files from one cached repository snapshot."""

    files: tuple[Path, ...]
    revision: str | None
    snapshot: Path
    cache_dir: Path

    def file(self, name: str) -> Path | None:
        """Find an exact relative path, or an unambiguous basename."""
        exact = [p for p in self.files if p.relative_to(self.snapshot).as_posix() == name]
        if len(exact) == 1:
            return exact[0]
        by_name = [p for p in self.files if p.name == name]
        return by_name[0] if len(by_name) == 1 else None


def concrete_snapshot_files(
    snapshot: Path | str,
    patterns: Sequence[str] | None,
) -> tuple[Path, ...]:
    """Narrow one snapshot to real files, requiring every pattern to match.

    The paths returned remain inside the snapshot tree. Hugging Face normally
    materialises them as symlinks into ``blobs/``; resolving those symlinks
    would discard the snapshot/revision context needed for provenance.
    """
    root = Path(snapshot)
    if not root.is_dir():
        return ()
    candidates = sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    if patterns is None:
        return tuple(candidates)
    if not patterns:
        return ()

    selected: List[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = [
            path for path in candidates
            if fnmatch(path.relative_to(root).as_posix(), pattern)
        ]
        if not matches:
            return ()
        for path in matches:
            if path not in seen:
                seen.add(path)
                selected.append(path)
    return tuple(selected)


def resolve(
    repo: str,
    revision: str | None,
    patterns: Sequence[str] | None,
) -> ResolvedWeights | None:
    """Resolve cached model files without making a network request.

    A result is atomic: every requested pattern came from the same snapshot
    and therefore the same resolved revision. Missing or incomplete cache
    state returns ``None``; it never falls forward to another revision or
    combines a model from one cache with auxiliary files from another.
    """
    if not repo or "/" not in repo:
        return None

    from huggingface_hub import snapshot_download

    for cache_dir in weights_read_dirs():
        try:
            snapshot = Path(snapshot_download(
                repo_id=repo,
                revision=revision,
                cache_dir=str(cache_dir),
                allow_patterns=list(patterns) if patterns is not None else None,
                local_files_only=True,
            ))
        except Exception:
            # Cache misses and incomplete snapshots are ordinary availability
            # states. The resolver is intentionally unable to repair them.
            continue
        files = concrete_snapshot_files(snapshot, patterns)
        if not files:
            continue
        return ResolvedWeights(
            files=files,
            revision=revision_from_snapshot(snapshot),
            snapshot=snapshot,
            cache_dir=cache_dir,
        )
    return None
