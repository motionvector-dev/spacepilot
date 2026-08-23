#!/usr/bin/env python3
"""Escaping tests for the studio frontend.

There is no JS test harness in this repo, so esc() is exercised through node
and the innerHTML templates are checked by inspection. The second test is the
regression guard: it fails if server data is interpolated raw again.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUTO_ROOT = Path(__file__).resolve().parent.parent
APP_JS = PLUTO_ROOT / "web" / "app.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _esc_source():
    match = re.search(r"^function esc\(value\) \{.*?^\}", APP_JS.read_text(), re.S | re.M)
    assert match, "esc() helper is missing from app.js"
    return match.group(0)


def test_esc_neutralises_html_payloads():
    script = _esc_source() + r"""
const cases = [
  ['<img src=x onerror=alert(1)>', '&lt;img src=x onerror=alert(1)&gt;'],
  ['"><script>alert(1)<\/script>', '&quot;&gt;&lt;script&gt;alert(1)&lt;\/script&gt;'],
  ["' onmouseover='alert(1)", '&#39; onmouseover=&#39;alert(1)'],
  ['a & b', 'a &amp; b'],
  [null, ''],
  [undefined, ''],
  [42, '42'],
];
for (const [input, expected] of cases) {
  const got = esc(input);
  if (got !== expected) {
    console.error(`FAIL ${JSON.stringify(input)}: got ${JSON.stringify(got)} want ${JSON.stringify(expected)}`);
    process.exit(1);
  }
}
console.log('ok');
"""
    result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ok" in result.stdout


def test_server_data_is_never_interpolated_raw_into_innerhtml():
    """Fail if a scene/asset field reaches an innerHTML template unescaped."""
    source = APP_JS.read_text()
    templates = re.findall(r"innerHTML\s*=\s*`(.*?)`", source, re.S)
    assert templates, "no innerHTML templates found; did app.js move?"

    offenders = []
    for template in templates:
        for expression in re.findall(r"\$\{([^}]*)\}", template):
            if not re.search(r"\b(scene|asset)\.", expression):
                continue
            if "esc(" in expression or "encodeURIComponent(" in expression:
                continue
            offenders.append(expression.strip())

    assert not offenders, "unescaped server data in innerHTML: " + "; ".join(offenders)


def test_syntax_is_valid():
    result = subprocess.run([shutil.which("node"), "--check", str(APP_JS)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_sidebar_format_time():
    """Verify the formatTime logic added to sidebar.js"""
    import re
    sidebar = PLUTO_ROOT / "web" / "sidebar.js"
    source = sidebar.read_text()
    match = re.search(r"^    function formatTime\(totalSeconds\) \{.*?^\s*\}", source, re.S | re.M)
    assert match, "formatTime() helper is missing from sidebar.js"
    script = match.group(0) + r"""
const cases = [
  [0, '00:00'],
  [14, '00:14'],
  [614, '10:14'],
  [3614, '1:00:14'],
  [7214, '2:00:14'],
  [NaN, '00:00'],
  [-10, '00:00'],
  ['invalid', '00:00'],
  [null, '00:00'],
  [undefined, '00:00']
];
for (const [input, expected] of cases) {
  const got = formatTime(input);
  if (got !== expected) {
    console.error(`FAIL ${input}: got ${got} want ${expected}`);
    process.exit(1);
  }
}
console.log('ok');
"""
    result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ok" in result.stdout


def test_cockpit_syntax():
    cockpit_js = PLUTO_ROOT / "web" / "cockpit.js"
    result = subprocess.run([shutil.which("node"), "--check", str(cockpit_js)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_create_js_syntax():
    create_js = PLUTO_ROOT / "web" / "create.js"
    result = subprocess.run([shutil.which("node"), "--check", str(create_js)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
