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

import pathlib
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
              "text", "vision"}
BACKENDS = {"metal", "cuda", "rocm", "cpu"}
METHODS = {"pip"}


class RuntimeError_(ValueError):
    """A runtime file is wrong. Always names the file."""


@dataclass(frozen=True)
class Install:
    method: str
    package: str
    min_version: Optional[str] = None
    checked: Optional[str] = None

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
    verify_import: str
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

    verify = _req(raw, "verify", where)
    imp = _req(verify, "import", f"{where}.verify")

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
        ),
        verify_import=str(imp),
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

def interpreter() -> str:
    """The interpreter this project runs under.

    A runtime installed into some other Python is not installed as far as this
    project is concerned, so every check and every install names it explicitly.
    """
    from spacepilot.paths import env_value
    return env_value("SPACEPILOT_PYTHON", "PLUTO_PYTHON") or sys.executable


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

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def check(r: Runtime, py: Optional[str] = None) -> Status:
    """Import it in the real interpreter and report the version it actually has.

    Nothing here trusts a package manager's exit code. A wheel can unpack and
    still fail to import — a compiled extension built for a different CPU, a
    missing system library, a partially written install.
    """
    py = py or interpreter()
    compatible, note = python_ok(r, py)

    probe = (
        f"import importlib,sys\n"
        f"m=importlib.import_module({r.verify_import!r})\n"
        f"print(getattr(m,'__version__', '') or 'unknown')"
    )
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


def preview(r: Runtime, py: Optional[str] = None, timeout: int = 300) -> Impact:
    """Resolve the install without performing it, and diff against what is here."""
    import json
    import tempfile

    py = py or interpreter()
    spec = r.install.package
    if r.install.min_version:
        spec = f"{spec}>={r.install.min_version}"

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        report = fh.name
    proc = subprocess.run(
        [py, "-m", "pip", "install", "--dry-run", "--quiet", "--report", report, spec],
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


def install_command(r: Runtime, py: Optional[str] = None) -> List[str]:
    """The exact argv that would run. Callers show this before running it."""
    spec = r.install.package
    if r.install.min_version:
        spec = f"{spec}>={r.install.min_version}"
    return [py or interpreter(), "-m", "pip", "install", spec]


def install(r: Runtime, py: Optional[str] = None, timeout: int = 900) -> Status:
    """Install, then verify by importing. The install is not the evidence."""
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
