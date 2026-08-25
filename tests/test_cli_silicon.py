"""`spacepilot silicon` has to show provenance, and has to show silence.

The silicon registry exists because a vendor claim and a press report are not
the same kind of fact, and because "the vendor publishes no figure" is not the
same as "the figure is zero". A CLI that flattens either distinction throws away
the only thing the registry was built to keep.

Every test here has been watched fail against a deliberately broken cli.py.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from spacepilot.cli import cmd_silicon
from spacepilot.pluto.silicon import silicon

ROOT = Path(__file__).resolve().parents[1]

# Spelled out, not imported from cli.py on purpose. Asserting `NOT_PUBLISHED in
# output` passes for any value of the constant, including "" — which is the
# empty cell this test exists to forbid. Watched happen: blanking the constant
# left all three null tests green. The words a reader sees are the contract, so
# the words are what the test names.
NOT_PUBLISHED = "not published"
REPORTED_MARK = "*"

CLAIM_FIELDS = ("memory_bytes", "bandwidth_bytes_per_sec",
                "npu_tops", "power_watts", "price_usd")


def _run(capsys, part_id=None, as_json=False):
    rc = cmd_silicon(argparse.Namespace(part_id=part_id, json=as_json))
    return rc, capsys.readouterr().out


def _row(text, part_id):
    """The one table line for a part, so a cell can be read in isolation."""
    rows = [ln for ln in text.splitlines() if f" {part_id} " in ln]
    assert len(rows) == 1, f"expected one row for {part_id}, got {len(rows)}"
    return rows[0]


# ── the table ────────────────────────────────────────────────────────────────

def test_list_shows_every_part_in_the_registry(capsys):
    parts = silicon()
    assert len(parts) >= 4, "the registry looks empty; this test would prove nothing"
    rc, out = _run(capsys)
    assert rc == 0
    for part_id in parts:
        assert part_id in out, f"{part_id} is in the registry but not in the table"


def test_list_is_the_default_and_the_word_list_means_the_same(capsys):
    _, bare = _run(capsys)
    _, spelled = _run(capsys, part_id="list")
    assert bare == spelled


def test_no_part_is_named_list():
    """`silicon list` reserves the word, so a part called `list` would be
    unreachable by id — the same trap `models list` already carries."""
    assert "list" not in silicon()


def test_the_table_names_its_columns(capsys):
    _, out = _run(capsys)
    header = next(ln for ln in out.splitlines() if "PART" in ln)
    for column in ("KIND", "PART", "AVAILABILITY", "MEMORY", "BANDWIDTH", "SOURCE"):
        assert column in header


def test_rows_are_sorted_by_kind_then_id(capsys):
    _, out = _run(capsys)
    parts = silicon()
    seen = []
    for line in out.splitlines():
        for part in parts.values():
            if f" {part.id} " in line:
                seen.append((part.kind, part.id))
    assert seen == sorted(seen), f"table is out of order: {seen}"


# ── provenance is visible, not hidden ────────────────────────────────────────

def test_a_reported_figure_is_marked_and_a_declared_one_is_not(capsys):
    """The distinction the registry exists for has to survive to the screen.

    A row whose figures all came from the vendor must not wear the mark, and a
    row whose figures came from a publication must.
    """
    parts = silicon()
    _, out = _run(capsys)

    vendor_only, reported_only = [], []
    for part in parts.values():
        claims = [c for c in (getattr(part, f) for f in CLAIM_FIELDS) if c]
        shown = [c for c in (part.memory_bytes, part.bandwidth_bytes_per_sec) if c]
        if not claims or not shown:
            continue
        if all(c.is_vendor for c in claims):
            vendor_only.append(part)
        elif not any(c.is_vendor for c in claims):
            reported_only.append(part)

    assert vendor_only, "no all-declared part; this test proves nothing without one"
    assert reported_only, "no all-reported part; this test proves nothing without one"

    for part in vendor_only:
        row = _row(out, part.id)
        assert REPORTED_MARK not in row, (
            f"{part.id} publishes its own figures but the row marks them as reported"
        )
        assert "declared" in row
    for part in reported_only:
        row = _row(out, part.id)
        assert REPORTED_MARK in row, (
            f"{part.id} carries only reported figures and the row does not say so"
        )
        assert "reported" in row


def test_the_table_explains_its_own_mark(capsys):
    """A sigil nobody can decode is worse than no sigil."""
    _, out = _run(capsys)
    legend = out[out.rindex("`spacepilot silicon <id>`"):]
    assert REPORTED_MARK in legend
    assert "reported" in legend
    assert "vendor" in legend


# ── null is a real value ─────────────────────────────────────────────────────

def test_an_absent_figure_reads_as_not_published(capsys):
    parts = silicon()
    _, out = _run(capsys)

    silent = [p for p in parts.values()
              if p.bandwidth_bytes_per_sec is None or p.memory_bytes is None]
    assert silent, "no part is missing a figure; this test proves nothing without one"
    for part in silent:
        assert NOT_PUBLISHED in _row(out, part.id), (
            f"{part.id} has an unpublished figure that the table left blank"
        )


def test_an_absent_figure_is_never_printed_as_zero(capsys):
    """`0 GB/s` is a claim. Nobody made it."""
    _, out = _run(capsys)
    zero = re.search(r"(?<![\d.])0(\.0)?\s*(GB|TB|TOPS|W)\b", out)
    assert zero is None, f"a figure rendered as zero: {zero.group(0)!r}"


def test_the_table_says_what_not_published_means(capsys):
    _, out = _run(capsys)
    legend = out[out.rindex("`spacepilot silicon <id>`"):]
    assert NOT_PUBLISHED in legend
    assert "not zero" in legend


# ── one part, in full ────────────────────────────────────────────────────────

def test_detail_shows_every_claim_with_its_date_and_link(capsys):
    for part in silicon().values():
        rc, out = _run(capsys, part_id=part.id)
        assert rc == 0
        assert part.name in out and f"[{part.id}]" in out
        for field in CLAIM_FIELDS:
            claim = getattr(part, field)
            if claim is None:
                continue
            assert claim.checked in out, f"{part.id}.{field} printed without its date"
            assert claim.url in out, f"{part.id}.{field} printed without its source link"
            assert claim.source in out, f"{part.id}.{field} printed without its source kind"


def test_detail_names_the_figures_nobody_published(capsys):
    parts = silicon()
    silent = [p for p in parts.values()
              if any(getattr(p, f) is None for f in CLAIM_FIELDS)]
    assert silent, "every part carries every figure; this test proves nothing"
    for part in silent:
        _, out = _run(capsys, part_id=part.id)
        missing = [f for f in CLAIM_FIELDS if getattr(part, f) is None]
        assert out.count(NOT_PUBLISHED) >= len(missing), (
            f"{part.id} has {len(missing)} unpublished figures and the detail "
            f"view accounts for fewer"
        )


def test_detail_does_not_print_the_table(capsys):
    _, out = _run(capsys, part_id="hbf")
    assert "AVAILABILITY" not in out


def test_an_unknown_part_id_fails_and_says_how_to_list(capsys):
    rc, out = _run(capsys, part_id="not-a-real-part")
    assert rc == 1
    assert "not-a-real-part" in out
    assert "spacepilot silicon" in out


# ── json ─────────────────────────────────────────────────────────────────────

def test_json_list_carries_every_part_and_every_source(capsys):
    _, out = _run(capsys, as_json=True)
    data = json.loads(out)
    assert {p["id"] for p in data["parts"]} == set(silicon())
    for raw in data["parts"]:
        for field in CLAIM_FIELDS:
            claim = raw[field]
            if claim is None:
                continue
            assert claim["source"] in ("declared", "reported")
            assert claim["checked"]
            assert claim["url"].startswith("https://")


def test_json_keeps_an_absent_figure_as_null(capsys):
    """Not 0, not omitted. A consumer must be able to tell the difference."""
    _, out = _run(capsys, as_json=True)
    by_id = {p["id"]: p for p in json.loads(out)["parts"]}
    for part in silicon().values():
        for field in CLAIM_FIELDS:
            if getattr(part, field) is None:
                assert by_id[part.id][field] is None, (
                    f"{part.id}.{field} is unpublished but JSON gave it a value"
                )


def test_json_detail_is_one_part(capsys):
    _, out = _run(capsys, part_id="hbf", as_json=True)
    data = json.loads(out)
    assert data["id"] == "hbf"
    assert "parts" not in data


# ── the verb is actually wired up ────────────────────────────────────────────

@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "spacepilot/cli.py", "silicon"],
        [sys.executable, "-m", "spacepilot.cli", "silicon", "list"],
        [sys.executable, "spacepilot/cli.py", "silicon", "hbf"],
        [sys.executable, "spacepilot/cli.py", "silicon", "--json"],
    ],
    ids=["bare", "as-a-module", "one-part", "json"],
)
def test_silicon_runs_from_the_command_line(argv):
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr[-2000:]
    assert proc.stdout.strip()
