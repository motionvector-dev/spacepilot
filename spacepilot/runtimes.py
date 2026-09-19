"""Runtimes: the packages that actually execute a model.

The model registry answers "which weights". This answers "with what". They are
different questions and conflating them is why nobody can tell you how to run a
model you have already downloaded — the weights are the easy half.

A runtime is installed, not downloaded, so the honesty rules differ slightly:
what matters is not where a number came from but whether the thing is really
importable *right now, in the interpreter this project uses*. pip exiting zero
proves a wheel was unpacked. It does not prove the package imports, that its
compiled extension matches this CPU, or that it found a GPU.
"""

from __future__ import annotations

import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from spacepilot.paths import shipped_dir

SCHEMA_VERSION = 1
RUNTIME_DIR = shipped_dir("runtimes")

# `transcription` is audio in, text out. `vad` is audio in, timings out —
# not inference in the sense the rest of this list means, but a runtime a
# user installs and a capability they ask for, so it is named rather than
# folded into "audio".
MODALITIES = {"video", "image", "audio", "speech", "transcription", "vad",
              "text", "vision", "embedding"}
BACKENDS = {"metal", "cuda", "rocm", "cpu"}
# "pip" installs into this project's interpreter, the way every runtime so
# far has. "script" runs a pinned install script and verifies by shelling
# out to the resulting binary's own --version -- for a runtime that ships
# no Python package at all, like a Swift or Go CLI distributed as a release
# tarball. Nothing here means "trust the installer" any more than pip does:
# check() still proves the binary runs, it just cannot prove it by import.
METHODS = {"pip", "script"}


class RuntimeError_(ValueError):
    """A runtime file is wrong. Always names the file."""


@dataclass(frozen=True)
class Install:
    method: str
    package: str
    min_version: Optional[str] = None
    checked: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    # The real pip install target, when it differs from `package` -- a git
    # checkout pinned to a commit SHA (`edge0 @ git+https://...@<sha>`),
    # for example. `package` stays the plain distribution name so version
    # lookups (importlib.metadata.version) still resolve correctly; `source`
    # is what actually gets passed to pip. method == "pip" only.
    source: Optional[str] = None
    # The pinned install script URL. method == "script" only -- e.g. a
    # release-tagged `install.sh` from the runtime's own repo, never `main`.
    script_url: Optional[str] = None
    # method == "pip" only. Installs into a dedicated venv under
    # `spacepilot.paths.runtime_env_dir(id)` instead of this project's shared
    # interpreter -- for a runtime whose own pins would otherwise downgrade a
    # package another runtime here needs (edge0 pins `mlx-lm==0.31.0`
    # exactly; this registry's own mlx-lm recipe asks for `>=0.31.3`). mflux
    # runs the same way in spirit but predates this flag -- it is reached
    # through a hand-managed conda env via `_EXTERNAL_ENTRY_POINT` instead;
    # `isolated` is the flag for a runtime this project creates and manages
    # itself.
    isolated: bool = False
    # method == "script" only. Positional arguments the install script
    # needs, as format() templates -- e.g. ["{model_dir}"] for bitnet-cpp's
    # tools/install-bitnet-cpp.sh, whose own `${1:?usage...}` guard refuses
    # to run without the directory containing the fetched GGUF. Empty for a
    # script that takes no arguments (llama-cpp-prism, desert-ant).
    script_args: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Runtime:
    id: str
    name: str
    summary: str
    homepage: Optional[str]
    serves: List[str]
    backends: List[str]
    license: str
    install: Install
    # Exactly one of these is set, matching install.method: `verify_import`
    # for "pip" (a module this interpreter can import), `verify_binary` for
    # "script" (a CLI name resolved on PATH and run with --version).
    verify_import: Optional[str] = None
    verify_binary: Optional[str] = None
    python_requires: Optional[str] = None
    runs: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "install"}
        d["install"] = self.install.to_dict()
        return d


def _req(d: Dict[str, Any], key: str, where: str) -> Any:
    if key not in d or d[key] is None:
        raise RuntimeError_(f"{where}: missing required field '{key}'")
    return d[key]


def parse_runtime(raw: Dict[str, Any], where: str) -> Runtime:
    if raw.get("schema") != SCHEMA_VERSION:
        raise RuntimeError_(f"{where}: schema is {raw.get('schema')!r}, this build reads {SCHEMA_VERSION}")

    serves = list(_req(raw, "serves", where))
    bad = set(serves) - MODALITIES
    if bad:
        raise RuntimeError_(f"{where}: unknown modalities {sorted(bad)}")

    backends = list(_req(raw, "backends", where))
    bad = set(backends) - BACKENDS
    if bad:
        raise RuntimeError_(f"{where}: unknown backends {sorted(bad)}")

    inst = _req(raw, "install", where)
    method = _req(inst, "method", f"{where}.install")
    if method not in METHODS:
        raise RuntimeError_(f"{where}.install: method '{method}' not one of {sorted(METHODS)}")

    if method == "script":
        script_url = str(_req(inst, "script_url", f"{where}.install"))
    else:
        script_url = inst.get("script_url")

    verify = _req(raw, "verify", where)
    if method == "script":
        verify_binary = str(_req(verify, "binary", f"{where}.verify"))
        verify_import = None
    else:
        verify_import = str(_req(verify, "import", f"{where}.verify"))
        verify_binary = verify.get("binary")

    return Runtime(
        id=str(_req(raw, "id", where)),
        name=str(_req(raw, "name", where)),
        summary=str(_req(raw, "summary", where)).strip(),
        homepage=raw.get("homepage"),
        serves=serves,
        backends=backends,
        license=str(_req(raw, "license", where)),
        install=Install(
            method=method,
            package=str(_req(inst, "package", f"{where}.install")),
            min_version=inst.get("min_version"),
            checked=inst.get("checked"),
            constraints=list(inst.get("constraints") or []),
            source=inst.get("source"),
            script_url=script_url,
            isolated=bool(inst.get("isolated", False)),
            script_args=list(inst.get("args") or []),
        ),
        verify_import=verify_import,
        verify_binary=verify_binary,
        python_requires=raw.get("python_requires"),
        runs=list(raw.get("runs") or []),
        notes=(raw.get("notes") or "").strip() or None,
    )


def load_runtimes(directory: Path | str | None = None) -> Dict[str, Runtime]:
    d = Path(directory or RUNTIME_DIR)
    if not d.is_dir():
        raise RuntimeError_(f"runtime directory not found: {d}")
    out: Dict[str, Runtime] = {}
    for path in sorted(d.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise RuntimeError_(f"{path.name}: not valid YAML — {e}") from e
        r = parse_runtime(raw, path.name)
        if r.id in out:
            raise RuntimeError_(f"{path.name}: duplicate runtime id '{r.id}'")
        out[r.id] = r
    if not out:
        raise RuntimeError_(f"no runtime files in {d}")
    return out


_cache: Optional[Dict[str, Runtime]] = None


def runtimes() -> Dict[str, Runtime]:
    global _cache
    if _cache is None:
        _cache = load_runtimes()
    return _cache


# ------------------------------------------------------------------- status

_CONSOLE_SCRIPT_EXEC_RE = re.compile(r"exec'?\s+'([^']+)'")


def _spacepilot_console_python(which_fn=None) -> Optional[str]:
    """The interpreter behind the installed `spacepilot` console script --
    the same interpreter `spacepilot run <cli>` actually executes with.

    This is the one truth `fly.py` and `spacepilot runtimes list` have to
    agree on. Without it, `interpreter()` fell back to `sys.executable` --
    the interpreter of whichever process happens to be running *this* code,
    which differs between the two callers: `spacepilot runtimes list` runs
    inside the pipx-installed console script's own venv, so its
    `sys.executable` is correct by accident, while `tools/fly.py` is
    normally launched as `python3 tools/fly.py`, under the ambient
    interpreter -- not the one `fly.py`'s own flight command
    (`spacepilot run <cli> ...`) subprocesses into. A shared-interpreter
    runtime (mlx-lm, whisper-cpp) installed by one caller's `interpreter()`
    and checked by the other's could disagree on "installed" even though
    both point at the same package -- see docs/registry/flights.md, "PR
    #137 said mlx-lm and whisper-cpp were installed" and
    tests/test_runtimes.py's console-python tests for the story.

    A pipx (or venv `console_scripts`) shim's first line is
    `exec '<python>' "$0" "$@"`; this reads that path straight out of the
    shim rather than trusting `sys.executable`, so both callers resolve to
    the identical interpreter regardless of which one is running. Returns
    None when there is no `spacepilot` on PATH or its shim does not match
    that shape -- callers fall back to `sys.executable`, never raise.
    """
    which_fn = which_fn or shutil.which
    exe = which_fn("spacepilot")
    if not exe:
        return None
    try:
        text = Path(exe).read_text(errors="ignore")
    except OSError:
        return None
    m = _CONSOLE_SCRIPT_EXEC_RE.search(text)
    if not m:
        return None
    candidate = m.group(1)
    return candidate if Path(candidate).is_file() else None


def interpreter(cfg: Optional[Dict[str, Any]] = None) -> str:
    """The interpreter this project runs under.

    A runtime installed into some other Python is not installed as far as this
    project is concerned, so every check and every install names it explicitly.

    Resolution order: an explicit override (`SPACEPILOT_PYTHON`/legacy
    `PLUTO_PYTHON`, or a configured `python_bin`) always wins. Absent one,
    this resolves the installed `spacepilot` console script's own
    interpreter (`_spacepilot_console_python`) rather than `sys.executable`
    -- see that function's docstring for why the two can otherwise disagree
    across callers. `sys.executable` is the last resort, only when no
    `spacepilot` console script can be found on PATH at all.
    """
    from spacepilot.paths import env_value
    configured = (cfg or {}).get("python_bin")
    explicit = (
        env_value("SPACEPILOT_PYTHON", "PLUTO_PYTHON")
        or (str(configured) if configured else None)
    )
    if explicit:
        return explicit
    return _spacepilot_console_python() or sys.executable


def python_ok(r: Runtime, py: Optional[str] = None) -> tuple[bool, str]:
    """Whether this interpreter satisfies the runtime's declared requirement."""
    if not r.python_requires:
        return True, ""
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
    except ImportError:
        return True, ""  # cannot check; do not block on a missing checker

    out = subprocess.run(
        [py or interpreter(), "-c", "import platform;print(platform.python_version())"],
        capture_output=True, text=True,
    )
    ver = out.stdout.strip()
    if not ver:
        return True, ""
    try:
        if Version(ver) in SpecifierSet(r.python_requires):
            return True, ver
        return False, f"needs Python {r.python_requires}; this interpreter is {ver}"
    except Exception:
        return True, ver


@dataclass
class Status:
    runtime_id: str
    installed: bool
    version: Optional[str] = None
    reason: Optional[str] = None
    # Present and importable, but older than the registry asks for. Distinct
    # from missing: the import works, so a caller that only checks `installed`
    # will happily run against an API that may not exist yet.
    below_minimum: bool = False
    wanted_version: Optional[str] = None
    python_compatible: bool = True
    python_note: Optional[str] = None
    interpreter: Optional[str] = None
    # Installed in its own environment, reached as a subprocess rather than
    # imported here. mflux runs this way on purpose — installing it into the
    # project interpreter downgrades opencv-python.
    external: bool = False
    external_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


# Runtimes that deliberately live in their own environment and are reached as
# a subprocess, keyed to the CLI entry point whose presence proves the install.
_EXTERNAL_ENTRY_POINT = {"mflux": "mflux-generate"}


def external_binary(r: Runtime, cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Resolved path of the runtime's CLI when it runs from its own environment.

    An import check against this project's interpreter says mflux is missing
    while `run image` in the same session executes it fine — the driver shells
    out to a separate conda env. This resolves the same bin dir the driver
    uses, so `runtimes check` and `run image` agree. Nothing is imported.
    """
    entry = _EXTERNAL_ENTRY_POINT.get(r.id)
    if not entry:
        return None
    from spacepilot.drivers.mflux_driver import mflux_bin_dir
    exe = Path(mflux_bin_dir(cfg)) / entry
    if exe.is_file() and os.access(exe, os.X_OK):
        return str(exe)
    return None


def isolated_env_dir(r: Runtime) -> Path:
    """Where a `install.isolated` runtime's own venv lives."""
    from spacepilot.paths import runtime_env_dir
    return runtime_env_dir(r.id)


def isolated_python(r: Runtime) -> Path:
    """The isolated venv's own interpreter."""
    return isolated_env_dir(r) / "bin" / "python"


def isolated_bin(r: Runtime, name: Optional[str] = None) -> Path:
    """One console-script entry point inside the isolated venv.

    Defaults to `install.package` -- right for edge0 (`pip install edge0`
    places an `edge0` entry point), wrong for any future isolated runtime
    whose CLI name differs from its distribution name, so callers with a
    different entry point pass `name` explicitly.
    """
    return isolated_env_dir(r) / "bin" / (name or r.install.package)


def _check_isolated(r: Runtime) -> Status:
    """Verify an `install.isolated` runtime inside its own venv.

    Never touches this project's interpreter -- there is nothing to import
    here on purpose, the same way an external mflux check never imports
    mflux into the calling process. A venv that has not been created yet is
    reported as not-installed with the fix (`spacepilot runtimes install
    <id>`), not as an error.
    """
    env_dir = isolated_env_dir(r)
    env_py = isolated_python(r)
    if not env_py.is_file():
        return Status(r.id, False, None,
                      f"no isolated environment yet at {env_dir} -- "
                      f"run `spacepilot runtimes install {r.id}`",
                      wanted_version=r.install.min_version, external=True)
    out = subprocess.run([str(env_py), "-c", _version_probe(r)],
                          capture_output=True, text=True, timeout=90)
    if out.returncode != 0:
        err = (out.stderr or "").strip().splitlines()
        reason = err[-1] if err else "import failed with no message"
        return Status(r.id, False, None, reason, wanted_version=r.install.min_version,
                      interpreter=str(env_py), external=True, external_path=str(env_py))
    version = out.stdout.strip() or "unknown"
    below = False
    if r.install.min_version and version != "unknown":
        try:
            from packaging.version import Version
            below = Version(version) < Version(r.install.min_version)
        except Exception:
            below = False
    return Status(r.id, True, version,
                  reason=(f"{version} is older than the {r.install.min_version} this "
                          f"registry was checked against") if below else None,
                  below_minimum=below, wanted_version=r.install.min_version,
                  interpreter=str(env_py), external=True, external_path=str(env_py))


def _install_isolated(r: Runtime, timeout: int = 900) -> Status:
    """Create the venv if it does not exist yet, then pip install into it.

    Idempotent: an existing venv is reused so a re-run only updates the pin,
    it does not rebuild the environment from scratch every time.
    """
    env_dir = isolated_env_dir(r)
    env_py = isolated_python(r)
    if not env_py.is_file():
        env_dir.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run([sys.executable, "-m", "venv", str(env_dir)],
                               capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            return Status(r.id, False, None,
                          tail[-1] if tail else f"venv creation exited {proc.returncode}",
                          external=True)

    proc = subprocess.run(install_command(r), capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return Status(r.id, False, None,
                      tail[-1] if tail else f"pip exited {proc.returncode}",
                      external=True, external_path=str(env_py))
    return check(r)


def _version_probe(r: Runtime) -> str:
    # mflux imports cleanly but carries no __version__, so fall back to the
    # installed distribution's metadata before settling for "unknown".
    return (
        f"import importlib,importlib.metadata,sys\n"
        f"m=importlib.import_module({r.verify_import!r})\n"
        f"v=getattr(m,'__version__', '')\n"
        f"if not v:\n"
        f"    try: v=importlib.metadata.version({r.install.package!r})\n"
        f"    except Exception: v=''\n"
        f"print(v or 'unknown')"
    )


def _external_status(r: Runtime, path: str) -> Status:
    env_py = Path(path).parent / "python"
    version = "unknown"
    if env_py.is_file():
        out = subprocess.run(
            [str(env_py), "-c", _version_probe(r)],
            capture_output=True, text=True, timeout=90,
        )
        if out.returncode == 0:
            version = out.stdout.strip() or "unknown"
    below = False
    if r.install.min_version and version != "unknown":
        try:
            from packaging.version import Version
            below = Version(version) < Version(r.install.min_version)
        except Exception:
            below = False
    return Status(
        r.id, True, version,
        reason=(f"{version} is older than the {r.install.min_version} this "
                f"registry was checked against") if below else None,
        below_minimum=below, wanted_version=r.install.min_version,
        interpreter=str(env_py) if env_py.is_file() else None,
        external=True, external_path=path,
    )


def _script_bin_env(r: Runtime) -> str:
    """Env var naming an explicit path to a script-installed runtime's
    binary -- the injection point tests use, mirroring `SPACEPILOT_MFLUX_BIN`
    for the pip-external route."""
    return f"SPACEPILOT_{r.id.upper().replace('-', '_')}_BIN"


def _check_script(r: Runtime, *, which_fn=None) -> Status:
    """Verify a script-installed runtime by shelling out to its own binary.

    There is no interpreter to import into, so "installed" here means: the
    named binary resolves (an explicit override env var first, then PATH)
    and it runs `--version` without dying. That is the same honesty bar
    `check()` holds pip runtimes to -- a binary that resolves and then
    segfaults is not installed either.
    """
    which_fn = which_fn or shutil.which
    binary = r.verify_binary or r.install.package
    override = os.environ.get(_script_bin_env(r))
    path = override or which_fn(binary)
    if not path or not os.path.isfile(path) or not os.access(path, os.X_OK):
        return Status(r.id, False, None,
                      f"'{binary}' not found on PATH -- {r.install.script_url or 'no install script registered'}",
                      wanted_version=r.install.min_version, external=True)
    out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        err = (out.stderr or out.stdout or "").strip().splitlines()
        reason = err[-1] if err else f"{binary} --version exited {out.returncode}"
        return Status(r.id, False, None, reason,
                      wanted_version=r.install.min_version, external=True, external_path=path)
    text = (out.stdout or out.stderr or "").strip()
    version = (text.splitlines()[0] if text else "unknown")
    return Status(r.id, True, version, wanted_version=r.install.min_version,
                  external=True, external_path=path)


def check(r: Runtime, py: Optional[str] = None,
          cfg: Optional[Dict[str, Any]] = None) -> Status:
    """Import it in the real interpreter and report the version it actually has.

    Nothing here trusts a package manager's exit code. A wheel can unpack and
    still fail to import — a compiled extension built for a different CPU, a
    missing system library, a partially written install. A runtime that lives
    in its own environment (see `external_binary`) counts as installed when
    its CLI resolves, because that is the route the drivers actually run.
    A "script" runtime never had a Python package to import in the first
    place, so it is checked by `_check_script` instead.
    """
    if r.install.method == "script":
        return _check_script(r)
    if r.install.isolated:
        return _check_isolated(r)

    py = py or interpreter(cfg)
    compatible, note = python_ok(r, py)

    probe = _version_probe(r)
    out = subprocess.run([py, "-c", probe], capture_output=True, text=True, timeout=90)
    if out.returncode == 0:
        version = out.stdout.strip() or "unknown"
        below = False
        if r.install.min_version and version != "unknown":
            try:
                from packaging.version import Version
                below = Version(version) < Version(r.install.min_version)
            except Exception:
                below = False
        return Status(r.id, True, version,
                      reason=(f"{version} is older than the {r.install.min_version} this "
                              f"registry was checked against") if below else None,
                      below_minimum=below, wanted_version=r.install.min_version,
                      python_compatible=compatible, python_note=note or None, interpreter=py)

    ext = external_binary(r, cfg)
    if ext:
        return _external_status(r, ext)

    err = (out.stderr or "").strip().splitlines()
    reason = err[-1] if err else "import failed with no message"
    return Status(r.id, False, None, reason, wanted_version=r.install.min_version,
                  python_compatible=compatible, python_note=note or None, interpreter=py)



@dataclass
class Impact:
    """What an install would change, resolved without changing anything.

    Installing a runtime into a shared environment is not additive. Resolving
    mflux downgrades opencv-python from 5.0 to 4.14 — nothing about the request
    says so, and whatever else in that environment needed opencv 5 breaks
    quietly, some time later, in unrelated code. A package manager will do this
    without comment; an installer that means to be trusted has to say it first.
    """
    new: List[tuple] = field(default_factory=list)       # (name, version)
    upgrades: List[tuple] = field(default_factory=list)  # (name, from, to)
    downgrades: List[tuple] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_disruptive(self) -> bool:
        return bool(self.downgrades)

    def to_dict(self) -> Dict[str, Any]:
        return {"new": self.new, "upgrades": self.upgrades,
                "downgrades": self.downgrades, "error": self.error,
                "is_disruptive": self.is_disruptive}


def _install_specs(r: Runtime) -> List[str]:
    # `source` (a pinned git checkout, say) is the real pip target; `package`
    # stays the plain distribution name so version lookups keep working.
    # A version floor makes no sense appended to a URL, so it is skipped
    # whenever a source is set -- the pin already is the version.
    spec = r.install.source or r.install.package
    if r.install.min_version and not r.install.source:
        spec = f"{spec}>={r.install.min_version}"
    return [spec, *r.install.constraints]


def preview(r: Runtime, py: Optional[str] = None, timeout: int = 300) -> Impact:
    """Resolve the install without performing it, and diff against what is here."""
    import json
    import tempfile

    if r.install.method == "script":
        # A script install never touches this project's Python environment --
        # there is nothing for pip to resolve and nothing to downgrade. An
        # empty, non-error Impact is the true answer, not a dodge: the caller
        # (`spacepilot runtimes install`) treats `error` as fatal and refuses
        # to proceed, so reporting "no changes here" is what lets a real
        # install happen at all for this method.
        return Impact()
    if r.install.isolated:
        # Same reasoning as the script method: an isolated install resolves
        # into its own fresh venv, never this project's interpreter, so there
        # is nothing here for a downgrade to threaten.
        return Impact()

    py = py or interpreter()
    specs = _install_specs(r)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        report = fh.name
    proc = subprocess.run(
        [py, "-m", "pip", "install", "--dry-run", "--quiet", "--report", report,
         *specs],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return Impact(error=tail[-1] if tail else f"pip exited {proc.returncode}")

    try:
        entries = json.loads(pathlib.Path(report).read_text()).get("install", [])
    except Exception as e:
        return Impact(error=f"could not read the resolution report: {e}")

    # Ask the target interpreter what it already has, not this one.
    names = [e["metadata"]["name"] for e in entries]
    probe = (
        "import importlib.metadata as md, json, sys\n"
        "out={}\n"
        "for n in json.loads(sys.argv[1]):\n"
        "    try: out[n]=md.version(n)\n"
        "    except Exception: out[n]=None\n"
        "print(json.dumps(out))"
    )
    have_proc = subprocess.run([py, "-c", probe, json.dumps(names)],
                               capture_output=True, text=True, timeout=90)
    try:
        have = json.loads(have_proc.stdout or "{}")
    except Exception:
        have = {}

    imp = Impact()
    for e in entries:
        name, ver = e["metadata"]["name"], e["metadata"]["version"]
        cur = have.get(name)
        if cur is None:
            imp.new.append((name, ver))
        elif cur != ver:
            try:
                from packaging.version import Version
                (imp.upgrades if Version(ver) > Version(cur) else imp.downgrades).append((name, cur, ver))
            except Exception:
                imp.upgrades.append((name, cur, ver))
    return imp


def install_command(r: Runtime, py: Optional[str] = None,
                     model_dir: Optional[Path | str] = None) -> List[str]:
    """The exact argv that would run. Callers show this before running it.

    `model_dir` fills a `{model_dir}` placeholder in `install.args` (see
    bitnet-cpp.yaml) -- the directory a flight has already downloaded the
    checkpoint into, known only after that download, never at parse time.
    Never raises for a missing `model_dir`: this is also what a preview
    (`spacepilot runtimes install <id>`, the MCP/API preview endpoints)
    calls before any download exists to name, so an unresolved placeholder
    is left as literal text (`{model_dir}`) rather than refusing to build a
    command at all. `tools/fly.py`'s `install_command_for` is the layer
    that actually refuses to run a real install with the placeholder
    unresolved -- see its docstring.
    """
    if r.install.method == "script":
        if r.install.script_args:
            formatted = [a.format(model_dir=str(model_dir)) if model_dir is not None else a
                         for a in r.install.script_args]
            args_str = " ".join(shlex.quote(a) for a in formatted)
            return ["sh", "-c", f"curl -fsSL {r.install.script_url} | sh -s -- {args_str}"]
        return ["sh", "-c", f"curl -fsSL {r.install.script_url} | sh"]
    if r.install.isolated:
        # Always the isolated venv's own interpreter -- an explicit `py`
        # never overrides it, the whole point of `isolated` is that this
        # runtime is never installed into whatever interpreter the caller
        # names.
        return [str(isolated_python(r)), "-m", "pip", "install", *_install_specs(r)]
    return [py or interpreter(), "-m", "pip", "install", *_install_specs(r)]


def install(r: Runtime, py: Optional[str] = None, timeout: int = 900,
            model_dir: Optional[Path | str] = None) -> Status:
    """Install, then verify by importing. The install is not the evidence."""
    if r.install.method == "script":
        proc = subprocess.run(install_command(r, model_dir=model_dir),
                               capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            return Status(r.id, False, None,
                          tail[-1] if tail else f"install script exited {proc.returncode}",
                          external=True)
        return check(r)
    if r.install.isolated:
        return _install_isolated(r, timeout=timeout)

    py = py or interpreter()
    compatible, note = python_ok(r, py)
    if not compatible:
        return Status(r.id, False, None, note, python_compatible=False,
                      python_note=note, interpreter=py)

    proc = subprocess.run(install_command(r, py), capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return Status(r.id, False, None,
                      tail[-1] if tail else f"pip exited {proc.returncode}",
                      python_compatible=True, python_note=note or None, interpreter=py)
    return check(r, py)


def for_backend(backend: Optional[str]) -> List[Runtime]:
    if not backend:
        return list(runtimes().values())
    return [r for r in runtimes().values() if backend in r.backends]


def serving(modality: str) -> List[Runtime]:
    return [r for r in runtimes().values() if modality in r.serves]
