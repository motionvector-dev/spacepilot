"""Renders and checkpoints stay inside the outputs directory.

The engines and the checkpoint sync service used to default to fixed paths
under /tmp. That is a symlink-attack surface on a shared machine, it collides
when two runs pick the same name, and it is not portable: /tmp is not where a
multi-gigabyte render belongs on a Linux GPU box.
"""

import re
from pathlib import Path

import pytest

from spacepilot.engines import HunyuanVideoEngine, LTXVideoEngine, WanVideoEngine
from spacepilot.pluto.core.config import get_settings
from spacepilot.pluto.services.checkpoint_sync import CheckpointSyncEngine

ENGINES = [LTXVideoEngine, WanVideoEngine, HunyuanVideoEngine]

SOURCES = [
    "spacepilot/engines/ltx_engine.py",
    "spacepilot/engines/wan_engine.py",
    "spacepilot/engines/hunyuan_engine.py",
    "spacepilot/pluto/services/checkpoint_sync.py",
]

REPO_ROOT = Path(__file__).resolve().parent.parent


def _assert_contained(path_str: str) -> Path:
    outputs_dir = get_settings().outputs_dir.resolve()
    path = Path(path_str).resolve()
    assert path.is_relative_to(outputs_dir), f"{path} escapes {outputs_dir}"
    return path


@pytest.mark.parametrize("engine_cls", ENGINES)
def test_generate_video_defaults_inside_outputs_dir(engine_cls):
    res = engine_cls().generate_video("a test prompt", seconds=0.5, draft_mode=True, mock=True)
    _assert_contained(res["video_path"])


@pytest.mark.parametrize("engine_cls", ENGINES)
def test_extend_video_defaults_inside_outputs_dir(engine_cls):
    res = engine_cls().extend_video("base.mp4", "a test prompt", seconds=0.5, mock=True)
    _assert_contained(res["video_path"])


@pytest.mark.parametrize("engine_cls", ENGINES)
def test_two_renders_do_not_collide(engine_cls):
    engine = engine_cls()
    first = engine.generate_video("p", seconds=0.5, draft_mode=True, mock=True)["video_path"]
    second = engine.generate_video("p", seconds=0.5, draft_mode=True, mock=True)["video_path"]
    assert first != second


def test_checkpoint_storage_inside_outputs_dir():
    engine = CheckpointSyncEngine()
    _assert_contained(engine.base_dir)


def test_checkpoint_restore_target_inside_outputs_dir():
    engine = CheckpointSyncEngine()
    meta = engine.create_snapshot("job-contained", 1, 1, 0.1, [])
    try:
        res = engine.restore_snapshot(meta.snapshot_id)
        _assert_contained(res["target_dir"])
    finally:
        engine.delete_snapshot(meta.snapshot_id)


@pytest.mark.parametrize("relpath", SOURCES)
def test_no_hardcoded_shared_temp_paths(relpath):
    """No render or checkpoint path is a fixed location in a world-writable dir."""
    text = (REPO_ROOT / relpath).read_text()
    offenders = re.findall(r'["\'](/tmp/[^"\']*)["\']', text)
    assert not offenders, f"{relpath} hardcodes shared temp paths: {offenders}"
