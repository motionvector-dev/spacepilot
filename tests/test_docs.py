#!/usr/bin/env python3
"""Tests for SpacePilot Public Documentation Portal."""

import os
import sys
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PLUTO_ROOT))
sys.path.append(str(PLUTO_ROOT / "spacepilot"))

from spacepilot.web_api import app

client = TestClient(app)


def test_docs_page_serves_html():
    """Test that GET /docs and GET /documentation return 200 with complete doc portal."""
    r_docs = client.get("/docs")
    assert r_docs.status_code == 200
    assert "SpacePilot Developer Portal" in r_docs.text or "SpacePilot" in r_docs.text
    assert "docs.js" in r_docs.text

    r_documentation = client.get("/documentation")
    assert r_documentation.status_code == 200
    assert "SpacePilot" in r_documentation.text


def test_docs_page_contains_core_architecture_sections():
    """Verify that all 6 critical sections and SVG visualizers are present in the HTML."""
    r = client.get("/docs")
    assert r.status_code == 200
    content = r.text

    # Section assertions
    assert "Quickstart" in content
    assert "Architecture" in content
    assert "Model Zoo" in content or "DiT" in content
    assert "FastMCP" in content
    assert "API Reference" in content or "REST API" in content
    assert "SkyPilot" in content or "Spot" in content

    # SVG Diagram assertions
    assert "<svg" in content
    assert "probe-vram" in content


def test_docs_js_syntax_is_valid():
    """Verify web/docs.js syntax with node."""
    docs_js_path = PLUTO_ROOT / "web" / "docs.js"
    assert docs_js_path.exists()

    res = subprocess.run(["node", "-c", str(docs_js_path)], capture_output=True, text=True)
    assert res.returncode == 0, f"Syntax error in web/docs.js: {res.stderr}"
