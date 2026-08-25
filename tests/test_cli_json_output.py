"""Every read verb's --json emits exactly one parseable JSON document on stdout.

`probe --json` used to print a save-hint trailer after the object, so
`| jq` failed on "Extra data". This walks the promise for every verb that
makes it: stdout parses as JSON, however the verb exits.
"""

import json
import subprocess
import sys

import pytest

VERBS = [
    ["probe", "--json"],
    ["models", "--json"],
    ["silicon", "--json"],
    ["runtimes", "list", "--json"],
    ["recipes", "list", "--json"],
    ["daemon", "status", "--json"],
]


@pytest.mark.parametrize("argv", VERBS, ids=[" ".join(v) for v in VERBS])
def test_json_stdout_is_a_single_document(argv):
    res = subprocess.run(
        [sys.executable, "-m", "spacepilot.cli", *argv],
        capture_output=True, text=True, timeout=120,
    )
    assert res.stdout.strip(), f"no stdout at all (stderr: {res.stderr[:200]})"
    doc = json.loads(res.stdout)  # raises on trailers or interleaved prose
    assert isinstance(doc, dict)
