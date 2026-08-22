#!/usr/bin/env python3
"""Comprehensive Unit and Integration Tests for Pluto DiT Video Engines.

Tests:
- EngineSpec dataclass and serialization
- LTX-Video 2.5, Wan2.1 (1.3B/14B), and HunyuanVideo engine adapters
- Dimension and frame count constraints
- Engine registry, alias resolution, and fallback behavior
- MCP Server tool integration (Wan and Hunyuan tools)
- Studio API multi-engine route and authentication gating
"""

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PLUTO_ROOT))
sys.path.append(str(PLUTO_ROOT / "src"))

from src.engines import (
    EngineSpec,
    BaseVideoEngine,
    LTXVideoEngine,
    WanVideoEngine,
    HunyuanVideoEngine,
    get_video_engine,
    list_video_engines,
    register_engine,
    normalize_engine_id,
    DEFAULT_ENGINE_ID,
)
from src.pluto_mcp_server import (
    pluto_generate_video_wan,
    pluto_generate_video_hunyuan,
)
from src.studio_api import app, STUDIO_TOKEN


client = TestClient(app)
AUTH_HEADERS = {"X-Pluto-Token": STUDIO_TOKEN}


# ─────────────────────────────────────────────────────────────────────────────
# 1. SPEC & DATACLASS TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_engine_spec_dataclass():
    spec = EngineSpec(
        engine_id="custom-dit",
        name="Custom DiT",
        parameters="7B",
        min_vram_gb=12.0,
        supported_aspects=["16:9", "9:16"],
        supports_i2v=True,
        supports_extend=False,
    )
    d = spec.to_dict()
    assert d["engine_id"] == "custom-dit"
    assert d["parameters"] == "7B"
    assert d["min_vram_gb"] == 12.0
    assert d["supports_i2v"] is True
    assert d["supports_extend"] is False


def test_ltx_video_engine_spec():
    engine = LTXVideoEngine()
    spec = engine.get_spec()
    assert spec.engine_id == "ltx-2.5"
    assert spec.name == "LTX-Video 2.5"
    assert spec.parameters == "13B"
    assert spec.min_vram_gb == 14.0
    assert "16:9" in spec.supported_aspects
    assert spec.supports_i2v is True
    assert spec.supports_extend is True


def test_wan_video_engine_specs():
    engine_13b = WanVideoEngine(model_size="1.3B")
    spec_13b = engine_13b.get_spec()
    assert spec_13b.engine_id == "wan-2.1-1.3b"
    assert spec_13b.parameters == "1.3B"
    assert spec_13b.min_vram_gb == 8.0
    assert spec_13b.supports_i2v is True

    engine_14b = WanVideoEngine(model_size="14B")
    spec_14b = engine_14b.get_spec()
    assert spec_14b.engine_id == "wan-2.1-14b"
    assert spec_14b.parameters == "14B"
    assert spec_14b.min_vram_gb == 24.0
    assert spec_14b.supports_i2v is True


def test_hunyuan_video_engine_spec():
    engine = HunyuanVideoEngine()
    spec = engine.get_spec()
    assert spec.engine_id == "hunyuan-video"
    assert "dual-stream" in spec.parameters
    assert spec.min_vram_gb == 32.0
    assert spec.supports_i2v is True
    assert spec.supports_extend is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONSTRAINTS & DIMENSIONS
# ─────────────────────────────────────────────────────────────────────────────

def test_ltx_constraints():
    engine = LTXVideoEngine()
    # Multiples of 32
    w, h = engine.adjust_dimensions(500, 300)
    assert w % 32 == 0
    assert h % 32 == 0
    # Frame count (8k + 1)
    assert (engine.adjust_frame_count(48) - 1) % 8 == 0
    assert engine.adjust_frame_count(97) == 97


def test_wan_constraints():
    engine = WanVideoEngine()
    # Multiples of 16
    w, h = engine.adjust_dimensions(500, 300)
    assert w % 16 == 0
    assert h % 16 == 0
    # Frame count (4k + 1)
    assert (engine.adjust_frame_count(48) - 1) % 4 == 0
    assert engine.adjust_frame_count(49) == 49


def test_hunyuan_constraints():
    engine = HunyuanVideoEngine()
    # Multiples of 16
    w, h = engine.adjust_dimensions(1280, 720)
    assert w % 16 == 0
    assert h % 16 == 0
    # Frame count (4k + 1)
    assert (engine.adjust_frame_count(48) - 1) % 4 == 0
    assert engine.adjust_frame_count(81) == 81


# ─────────────────────────────────────────────────────────────────────────────
# 3. REGISTRY & FALLBACK TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_registry_lookups_and_aliases():
    # Direct lookups
    assert isinstance(get_video_engine("ltx-2.5"), LTXVideoEngine)
    assert isinstance(get_video_engine("wan-2.1-1.3b"), WanVideoEngine)
    assert isinstance(get_video_engine("wan-2.1-14b"), WanVideoEngine)
    assert isinstance(get_video_engine("hunyuan-video"), HunyuanVideoEngine)

    # Aliases
    assert isinstance(get_video_engine("ltx"), LTXVideoEngine)
    assert isinstance(get_video_engine("ltx25"), LTXVideoEngine)
    assert isinstance(get_video_engine("wan"), WanVideoEngine)
    assert get_video_engine("wan").get_spec().parameters == "14B"
    assert get_video_engine("wan-1.3b").get_spec().parameters == "1.3B"
    assert isinstance(get_video_engine("hunyuan"), HunyuanVideoEngine)
    assert isinstance(get_video_engine("hunyuanvideo"), HunyuanVideoEngine)


def test_registry_fallback_on_unknown():
    # Fallback to default engine
    engine = get_video_engine("non_existent_engine_xyz")
    assert isinstance(engine, LTXVideoEngine)
    assert engine.get_spec().engine_id == DEFAULT_ENGINE_ID


def test_list_video_engines():
    specs = list_video_engines()
    ids = [s.engine_id for s in specs]
    assert "ltx-2.5" in ids
    assert "wan-2.1-1.3b" in ids
    assert "wan-2.1-14b" in ids
    assert "hunyuan-video" in ids


def test_custom_engine_registration():
    class MockCustomEngine(BaseVideoEngine):
        def get_spec(self):
            return EngineSpec("mock-custom", "Mock Custom", "1B", 4.0, ["16:9"], False, False)
        def generate_video(self, *args, **kwargs):
            return {"job_id": "custom-1", "status": "completed"}
        def extend_video(self, *args, **kwargs):
            return {"status": "completed"}

    register_engine("mock-custom", MockCustomEngine)
    engine = get_video_engine("mock-custom")
    assert isinstance(engine, MockCustomEngine)
    assert engine.get_spec().engine_id == "mock-custom"


# ─────────────────────────────────────────────────────────────────────────────
# 4. POLYMORPHIC GENERATION & EXTENSION
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("engine_id", ["ltx-2.5", "wan-2.1-1.3b", "wan-2.1-14b", "hunyuan-video"])
def test_engine_generate_and_extend(engine_id, tmp_path):
    engine = get_video_engine(engine_id)
    out_file = str(tmp_path / f"test_{engine_id}.mp4")

    res = engine.generate_video(
        prompt="A serene sunset over futuristic mountains",
        width=512,
        height=288,
        seconds=1.0,
        output_path=out_file,
        mock=True,
    )
    assert res["status"] == "completed"
    assert res["engine_id"] == engine.get_spec().engine_id
    assert "job_id" in res
    assert Path(out_file).exists()

    # Test extend
    ext_file = str(tmp_path / f"test_ext_{engine_id}.mp4")
    ext_res = engine.extend_video(
        video_path=out_file,
        prompt="The stars emerge in the twilight sky",
        seconds=1.0,
        output_path=ext_file,
        mock=True,
    )
    assert ext_res["status"] == "completed"
    assert ext_res["engine_id"] == engine.get_spec().engine_id
    assert Path(ext_file).exists()


def test_engine_image_to_video(tmp_path):
    img_file = tmp_path / "seed.png"
    # Valid 1x1 PNG bytes
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    with open(img_file, "wb") as f:
        f.write(valid_png)

    for eng_id in ["ltx-2.5", "wan-2.1-14b", "hunyuan-video"]:
        engine = get_video_engine(eng_id)
        out_file = str(tmp_path / f"i2v_{eng_id}.mp4")
        res = engine.generate_video(
            prompt="Animate this image into dynamic ocean waves",
            image_path=str(img_file),
            seconds=1.0,
            output_path=out_file,
            mock=True,
        )
        assert res["is_i2v"] is True
        assert res["status"] == "completed"


# ─────────────────────────────────────────────────────────────────────────────
# 5. MCP SERVER TOOLS
# ─────────────────────────────────────────────────────────────────────────────

def test_mcp_wan_video_generation():
    res = pluto_generate_video_wan(prompt="Cyberpunk flying car", model_size="14B")
    assert "job_id" in res
    assert res["status"] in ("processing", "completed")
    assert "wan" in res["engine_id"]

    res_13b = pluto_generate_video_wan(prompt="Cyberpunk flying car", model_size="1.3B")
    assert "job_id" in res_13b
    assert "wan" in res_13b["engine_id"]


def test_mcp_hunyuan_video_generation():
    res = pluto_generate_video_hunyuan(prompt="Ethereal space nebula", resolution="720p")
    assert "job_id" in res
    assert res["status"] in ("processing", "completed")
    assert res["engine_id"] == "hunyuan-video"


# ─────────────────────────────────────────────────────────────────────────────
# 6. STUDIO API MULTI-ENGINE ENDPOINTS & AUTH
# ─────────────────────────────────────────────────────────────────────────────

def test_api_list_engines():
    res = client.get("/api/engines")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert len(data["engines"]) >= 4
    ids = [e["engine_id"] for e in data["engines"]]
    assert "ltx-2.5" in ids
    assert "wan-2.1-14b" in ids
    assert "hunyuan-video" in ids


def test_api_generate_multi_engine_auth_gating():
    # 401 without auth header
    res_no_auth = client.post("/api/generate/multi-engine", json={"prompt": "test", "engine_id": "wan-2.1-14b"})
    assert res_no_auth.status_code == 401

    # 401 with invalid token
    res_bad_auth = client.post(
        "/api/generate/multi-engine",
        json={"prompt": "test", "engine_id": "wan-2.1-14b"},
        headers={"X-Pluto-Token": "invalid-token-12345"},
    )
    assert res_bad_auth.status_code == 401


@pytest.mark.parametrize("engine_id", ["ltx-2.5", "wan-2.1-1.3b", "wan-2.1-14b", "hunyuan-video"])
def test_api_generate_multi_engine_success(engine_id):
    res = client.post(
        "/api/generate/multi-engine",
        json={
            "prompt": "Cinematic shot of neon rain in Tokyo",
            "engine_id": engine_id,
            "seconds": 2.0,
            "draft_mode": True,
            "mock": True,
        },
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "queued"
    assert "job_id" in data
    assert "patch" in data
    assert data["engine_id"] == get_video_engine(engine_id).get_spec().engine_id
