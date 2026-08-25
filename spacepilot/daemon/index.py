"""A rebuildable, single-writer SQLite view of YAML and LOG facts.

SQLite is a derived index, never the source of truth.  Local YAML and verified
immutable LOG pages can be discarded and replayed into a temporary database;
the finished file is then atomically published.  A small queue owns every
write connection so concurrent daemon callers cannot create writer races.
"""

from __future__ import annotations

import json
import os
import queue
import sqlite3
import stat
import tempfile
import threading
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from spacepilot.daemon.log import (
    LogStore,
    LogError,
    _record_id,
    project_measurement,
    project_system,
    verify_page,
)
from spacepilot.paths import (
    daemon_index_path,
    daemon_log_replica_dir,
    read_roots,
)


INDEX_SCHEMA = 1


class IndexError(RuntimeError):
    """The derived index cannot be built or queried safely."""


def _schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode = DELETE;
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS records (
            record_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('system', 'measurement')),
            author_key_id TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS systems (
            record_id TEXT PRIMARY KEY REFERENCES records(record_id) ON DELETE CASCADE,
            author_key_id TEXT,
            system_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS measurements (
            record_id TEXT PRIMARY KEY REFERENCES records(record_id) ON DELETE CASCADE,
            author_key_id TEXT,
            system_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            measured_on TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS measurements_subject
            ON measurements(system_id, model_id, metric);
        CREATE INDEX IF NOT EXISTS measurements_date
            ON measurements(measured_on);
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema', ?)",
        (str(INDEX_SCHEMA),),
    )


def _insert(connection: sqlite3.Connection, record: Mapping[str, Any], *, author_key_id: str | None = None) -> None:
    kind = record.get("kind")
    payload = record.get("payload")
    if kind not in {"system", "measurement"} or not isinstance(payload, Mapping):
        raise IndexError("index record is not an allowlisted system/measurement")
    if kind == "system":
        payload = project_system(payload)
        if not payload.get("id"):
            raise IndexError("system projection has no id")
    else:
        payload = project_measurement(payload)
        required = ("system_id", "model_id", "metric", "value", "contention", "measured_on")
        if any(payload.get(field) is None for field in required):
            raise IndexError("measurement projection is missing required fields")
    record_id = str(record.get("record_id") or _record_id(kind, payload))
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    connection.execute(
        "INSERT OR IGNORE INTO records(record_id, kind, author_key_id, payload_json) VALUES(?, ?, ?, ?)",
        (record_id, kind, author_key_id or record.get("author_key_id"), payload_json),
    )
    # If a source was already indexed, preserving the first verified source is
    # useful: a relayed record must not overwrite its original author context.
    if kind == "system":
        connection.execute(
            "INSERT OR IGNORE INTO systems(record_id, author_key_id, system_id, payload_json) VALUES(?, ?, ?, ?)",
            (record_id, author_key_id or record.get("author_key_id"), str(payload.get("id", "")), payload_json),
        )
    else:
        connection.execute(
            """INSERT OR IGNORE INTO measurements(
                record_id, author_key_id, system_id, model_id, metric, value,
                measured_on, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record_id,
                author_key_id or record.get("author_key_id"),
                str(payload.get("system_id", "")),
                str(payload.get("variant_id") or payload.get("model_id", "")),
                str(payload.get("metric", "")),
                float(payload.get("value", 0.0)),
                payload.get("measured_on"),
                payload_json,
            ),
        )


def _yaml_records(root: Path, kind: str) -> Iterable[dict[str, Any]]:
    if not root.exists():
        return
    paths = sorted(root.glob("*.yaml")) if kind == "system" else sorted(root.rglob("*.yaml"))
    for path in paths:
        try:
            raw = yaml.safe_load(path.read_text()) or {}
            if not isinstance(raw, Mapping):
                continue
            payload = project_system(raw) if kind == "system" else project_measurement(raw)
            if not payload:
                continue
            if kind == "system" and not payload.get("id"):
                continue
            if kind == "measurement" and any(
                payload.get(field) is None
                for field in ("system_id", "model_id", "metric", "value", "contention", "measured_on")
            ):
                continue
            yield {"kind": kind, "payload": payload, "record_id": _record_id(kind, payload)}
        except (OSError, yaml.YAMLError, TypeError, ValueError, LogError):
            # One malformed local file must not make a rebuild publish a
            # database that is missing all other verified facts.
            continue


def _source_records(*, yaml_roots: Sequence[Path] | None,
                    log_root: Path | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if log_root is None:
        log_root = daemon_log_replica_dir()
    try:
        pages = LogStore(log_root).pages()
    except (OSError, LogError):
        pages = []
    # LOG first means a signed author's provenance survives a duplicate local
    # YAML copy with the same content hash.
    for page in pages:
        for record in page["records"]:
            records.append(dict(record))
    if yaml_roots is None:
        system_roots = read_roots("systems")
        measurement_roots = read_roots("measurements")
    else:
        system_roots = [Path(root) / "systems" for root in yaml_roots]
        measurement_roots = [Path(root) / "measurements" for root in yaml_roots]
    for root in system_roots:
        records.extend(_yaml_records(root, "system"))
    for root in measurement_roots:
        records.extend(_yaml_records(root, "measurement"))
    return records


def rebuild_index(*, destination: Path | None = None,
                  yaml_roots: Sequence[Path] | None = None,
                  log_root: Path | None = None) -> Path:
    """Replay YAML/LOG into a temporary SQLite DB and atomically publish it."""
    destination = Path(destination or daemon_index_path()).expanduser().resolve()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        connection = sqlite3.connect(temp)
        try:
            _schema(connection)
            for record in _source_records(yaml_roots=yaml_roots, log_root=log_root):
                try:
                    _insert(connection, record)
                except (IndexError, TypeError, ValueError):
                    continue
            connection.commit()
        finally:
            connection.close()
        os.chmod(temp, 0o600)
        os.replace(temp, destination)
        try:
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return destination


class IndexWriter:
    """One background SQLite writer fed by a thread-safe queue."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or daemon_index_path()).expanduser().resolve()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        if self.path.exists():
            info = self.path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise IndexError("index path is not a regular file")
            os.chmod(self.path, 0o600)
        self._queue: queue.Queue[tuple[str, Any, threading.Event, list[BaseException]]] = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="spacepilot-index-writer", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        connection = sqlite3.connect(self.path)
        try:
            _schema(connection)
            connection.commit()
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            while True:
                operation, value, done, errors = self._queue.get()
                if operation == "stop":
                    done.set()
                    return
                try:
                    if operation == "record":
                        _insert(connection, value)
                    elif operation == "rebuild":
                        for record in _source_records(yaml_roots=value[0], log_root=value[1]):
                            try:
                                _insert(connection, record)
                            except (IndexError, TypeError, ValueError):
                                continue
                    else:
                        raise IndexError(f"unknown index writer operation {operation!r}")
                    connection.commit()
                except BaseException as exc:  # propagate to caller, then keep queue alive
                    connection.rollback()
                    errors.append(exc)
                finally:
                    done.set()
        finally:
            connection.close()

    def submit(self, record: Mapping[str, Any]) -> None:
        self._call("record", dict(record))

    append = submit

    def rebuild(self, *, yaml_roots: Sequence[Path] | None = None, log_root: Path | None = None) -> None:
        self._call("rebuild", (yaml_roots, log_root))

    def _call(self, operation: str, value: Any) -> None:
        if self._closed:
            raise IndexError("index writer is closed")
        done = threading.Event()
        errors: list[BaseException] = []
        self._queue.put((operation, value, done, errors))
        done.wait()
        if errors:
            raise errors[0]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        done = threading.Event()
        self._queue.put(("stop", None, done, []))
        done.wait()
        self._thread.join(timeout=5)

    def __enter__(self) -> "IndexWriter":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class FleetIndex:
    """Read facade for the derived index, with an optional single writer."""

    def __init__(self, path: Path | None = None, *, writer: IndexWriter | None = None) -> None:
        self.path = Path(path or daemon_index_path()).expanduser().resolve()
        self.writer = writer

    def query(self, sql: str, parameters: Sequence[Any] = ()) -> list[dict[str, Any]]:
        if ";" in sql.strip().rstrip(";"):
            raise IndexError("index queries must contain one read-only statement")
        if not sql.lstrip().lower().startswith(("select", "pragma", "with")):
            raise IndexError("index queries are read-only")
        connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in connection.execute(sql, tuple(parameters))]
        except sqlite3.Error as exc:
            raise IndexError(str(exc)) from exc
        finally:
            connection.close()

    def systems(self) -> list[dict[str, Any]]:
        return self.query("SELECT * FROM systems ORDER BY system_id, record_id")

    def measurements(self) -> list[dict[str, Any]]:
        return self.query("SELECT * FROM measurements ORDER BY measured_on, record_id")


def build_index(**kwargs: Any) -> Path:
    return rebuild_index(**kwargs)


__all__ = ["INDEX_SCHEMA", "IndexError", "IndexWriter", "FleetIndex", "rebuild_index", "build_index"]
