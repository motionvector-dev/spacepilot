"""The fleet SQLite view is derived and has one writer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from spacepilot.daemon.identity import load_or_create
from spacepilot.daemon.index import FleetIndex, IndexWriter, rebuild_index
from spacepilot.daemon.log import LogStore, make_page, make_record
from spacepilot import paths


def test_rebuild_index_is_user_data_scoped_and_excludes_pictures(tmp_path, monkeypatch):
    data = tmp_path / "user-data"
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(data))
    yaml_root = tmp_path / "yaml"
    (yaml_root / "systems").mkdir(parents=True)
    (yaml_root / "measurements" / "box" / "demo").mkdir(parents=True)
    (yaml_root / "systems" / "box.yaml").write_text("id: box\nbackend: cpu\nnote: hide\n")
    (yaml_root / "measurements" / "box" / "demo" / "m.yaml").write_text(
        "schema: 1\nsystem_id: box\nmodel_id: demo\nmetric: seconds_per_image\n"
        "value: 2.5\ncontention: solo\nmeasured_on: '2026-08-25T00:00:00+00:00'\n"
        "interpreter: /private\nnote: hide\n"
    )
    destination = rebuild_index(
        destination=paths.daemon_index_path(), yaml_roots=[yaml_root], log_root=tmp_path / "empty-log"
    )
    assert destination == data / "daemon" / "index" / "fleet.sqlite3"
    assert destination.is_file()
    index = FleetIndex(destination)
    assert len(index.systems()) == 1
    assert len(index.measurements()) == 1
    assert "note" not in index.systems()[0]["payload_json"]
    assert "interpreter" not in index.measurements()[0]["payload_json"]
    assert not (data / "daemon" / "pictures").exists()


def test_single_writer_queue_serializes_concurrent_records(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(tmp_path / "data"))
    identity = load_or_create()
    path = tmp_path / "index.sqlite3"
    records = [
        make_record(identity, "system", {"id": f"box-{n}", "backend": "cpu"})
        for n in range(20)
    ]
    with IndexWriter(path) as writer:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(writer.submit, records))
    assert len(FleetIndex(path).systems()) == 20


def test_log_pages_are_replayed_into_index_with_author(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(tmp_path / "data"))
    identity = load_or_create()
    log_root = tmp_path / "log"
    record = make_record(identity, "measurement", {
        "schema": 1, "system_id": "box", "model_id": "demo", "metric": "seconds_per_image",
        "value": 3.0, "contention": "solo", "measured_on": "2026-08-25T00:00:00+00:00",
    })
    LogStore(log_root).ingest_page(make_page(identity, [record], epoch="e", sequence=0))
    destination = rebuild_index(destination=tmp_path / "derived.sqlite3", yaml_roots=[], log_root=log_root)
    rows = FleetIndex(destination).measurements()
    assert len(rows) == 1
    assert rows[0]["author_key_id"] == identity.key_id

