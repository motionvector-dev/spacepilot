"""tools/fly.py: plan ordering, runtime refusal, the dry-run flight of
Edge0-8B with no network, the idle/battery guards with faked probes, and the
manifest write shape validated against the real registry parser.

No test in this file downloads anything, runs `pmset`/`ioreg` for real
(every guard takes injected text), or leaves a git branch behind.
"""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import fly  # noqa: E402
from spacepilot.model_registry import load_registry  # noqa: E402


# --------------------------------------------------------------------- plan

def test_plan_lists_unflown_entries_smallest_first():
    rows = fly.plan_rows()
    assert rows, "expected at least one unflown variant in the shipped registry"
    sizes = [r.variant.download.value for r in rows]
    assert sizes == sorted(sizes)
    for row in rows:
        assert fly.is_unflown(row.variant)


def test_plan_refuses_entries_whose_runtime_is_not_installed():
    rows = fly.plan_rows()
    edge0 = next(r for r in rows if r.variant.id == "edge0-8b-a1b-preview-4bit")
    # edge0 is deliberately not installed into this project's shared
    # interpreter -- it pins mlx-lm==0.31.0 exactly, which downgrades the
    # mlx-lm runtime already installed here (see edge0.yaml's notes).
    assert edge0.runtime.installed is False
    assert edge0.runtime.install_cmd == "spacepilot runtimes install edge0"


def test_plan_shows_every_edge0_and_desert_ant_entry_as_flyable(monkeypatch):
    """Both runtimes are registered now (spacepilot/registry/runtimes/{edge0,
    desert-ant}.yaml); with the runtime reported installed, `plan` must not
    print BLOCKED for any Edge0 or Desert Ant entry it has a FlightPlan for.
    Align/shapes/tongue stay unmapped on purpose -- the CLI itself does not
    run them -- so they are excluded from this assertion, not silently
    expected to pass."""
    from spacepilot import runtimes as rt

    real_check = rt.check

    def fake_check(runtime, *a, **kw):
        if runtime.id in ("edge0", "desert-ant"):
            return rt.Status(runtime.id, True, "9.9.9")
        return real_check(runtime, *a, **kw)

    monkeypatch.setattr(fly.rt, "check", fake_check)

    rows = fly.plan_rows()
    edge0_ids = {"edge0-35b-a3b-preview-4bit", "edge0-8b-a1b-preview-4bit"}
    desert_ant_wired_ids = {
        "desert-ant-voz-1", "desert-ant-clear-1", "desert-ant-ear-1",
        "desert-ant-uhm-1", "desert-ant-redact-1", "desert-ant-title-1",
        "desert-ant-clips-1", "desert-ant-emo-1", "desert-ant-gist-1",
    }
    checked = 0
    for row in rows:
        if row.variant.id in edge0_ids or row.variant.id in desert_ant_wired_ids:
            assert row.runtime.installed, f"{row.variant.id} still BLOCKED"
            checked += 1
    assert checked == len(edge0_ids) + len(desert_ant_wired_ids), \
        "expected every wired Edge0/Desert Ant entry to appear in the plan"


def test_plan_still_blocks_the_desert_ant_models_the_cli_does_not_run():
    """align, tongue, and shapes have no runtime registered -- the CLI
    itself has no adapter for them -- so they stay BLOCKED regardless of
    whether desert-ant is installed."""
    rows = fly.plan_rows()
    for variant_id in ("desert-ant-align-1", "desert-ant-tongue-1", "desert-ant-shapes-1"):
        row = next(r for r in rows if r.variant.id == variant_id)
        assert row.runtime.installed is False
        assert row.runtime.install_cmd is None


def test_plan_never_marks_an_unflown_variant_as_flown():
    reg = load_registry()
    for v in reg.variants:
        if fly.is_unflown(v):
            assert v not in [r.variant for r in fly.plan_rows() if False]  # smoke: no crash
    # every variant either is unflown (has no speed) or plan skips it
    unflown_ids = {v.id for v in fly.unflown_variants()}
    plan_ids = {r.variant.id for r in fly.plan_rows()}
    assert unflown_ids == plan_ids


# ------------------------------------------------------------- dry-run flight

def test_dry_run_of_edge0_8b_logs_every_step_and_touches_no_network():
    fetch_calls = []

    class RecordingDryRunDownloader(fly.DryRunDownloader):
        def fetch(self, repo, revision, files):
            fetch_calls.append((repo, revision, files))
            return super().fetch(repo, revision, files)

    result = fly.fly_run(
        "edge0-8b-a1b-preview-4bit",
        dry_run=True,
        downloader=RecordingDryRunDownloader(),
        disk_check=lambda download_bytes: fly.GuardResult(True, "200.0 GB free now, 192.6 GB free after download (>= 40 GB floor)"),
        power_check=lambda: fly.GuardResult(True, "Now drawing from 'AC Power'"),
    )

    assert result.outcome == "dry-run"
    assert fetch_calls, "the (fake) downloader should still be asked what it would fetch"
    repo, revision, _files = fetch_calls[0]
    assert repo == "Edge0/Edge0-8B-A1B-preview"
    assert revision == "0bf17abed23b7de4b66e265a3848e80447ee7b41"

    joined = "\n".join(result.steps)
    assert "flying edge0-8b-a1b-preview-4bit" in joined
    assert "disk guard:" in joined
    assert "power guard:" in joined
    assert "flight command: spacepilot run text --model edge0-8b-a1b-preview-4bit --yes" in joined
    assert "dry-run: stopping before inference, measurement, registry write and commit" in joined
    # nothing about a commit or a registry write ever appears in a dry run
    assert "committed on" not in joined
    assert "registry updated" not in joined


def test_dry_run_of_desert_ant_voz_logs_the_real_command():
    fetch_calls = []

    class RecordingDryRunDownloader(fly.DryRunDownloader):
        def fetch(self, repo, revision, files):
            fetch_calls.append((repo, revision, files))
            return super().fetch(repo, revision, files)

    result = fly.fly_run(
        "desert-ant-voz-1",
        dry_run=True,
        downloader=RecordingDryRunDownloader(),
        disk_check=lambda download_bytes: fly.GuardResult(True, "200.0 GB free now, 199.5 GB free after download (>= 40 GB floor)"),
        power_check=lambda: fly.GuardResult(True, "Now drawing from 'AC Power'"),
    )

    assert result.outcome == "dry-run"
    assert fetch_calls
    repo, revision, _files = fetch_calls[0]
    assert repo == "desert-ant-labs/voz"
    assert revision == "78e93e14136909cd28977f7edcda4fa462ab58c8"

    joined = "\n".join(result.steps)
    assert "flying desert-ant-voz-1" in joined
    assert "flight command: spacepilot run transcribe --model desert-ant-voz-1 --yes" in joined
    assert "dry-run: stopping before inference, measurement, registry write and commit" in joined


def test_dry_run_never_calls_the_real_downloader():
    calls = {"n": 0}

    class ExplodingDownloader:
        def fetch(self, repo, revision, files):
            calls["n"] += 1
            raise AssertionError("dry-run must not use a real downloader by default")

    # dry_run=True with no downloader passed uses DryRunDownloader, not this one
    result = fly.fly_run(
        "edge0-8b-a1b-preview-4bit", dry_run=True,
        disk_check=lambda download_bytes: fly.GuardResult(True, "plenty free"),
        power_check=lambda: fly.GuardResult(True, "on AC"),
    )
    assert result.outcome == "dry-run"
    assert calls["n"] == 0


def test_dry_run_refuses_an_already_flown_variant():
    result = fly.fly_run("whisper-base-en")  # dry_run defaults True; this one is flown
    assert result.outcome == "refused"
    assert "already flown" in result.detail


def test_dry_run_refuses_an_unknown_model():
    result = fly.fly_run("not-a-real-model-id")
    assert result.outcome == "failed"


# --------------------------------------------------------------------- guards

def test_disk_guard_refuses_under_the_floor():
    result = fly.check_disk_guard(10 * 1024 ** 3, free_gb=45.0)  # 45 - 10 = 35 < 40
    assert result.ok is False
    result_ok = fly.check_disk_guard(10 * 1024 ** 3, free_gb=55.0)  # 55 - 10 = 45 >= 40
    assert result_ok.ok is True


def test_ac_power_guard_parses_pmset_output():
    on_ac = fly.on_ac_power("Now drawing from 'AC Power'\n -InternalBattery-0 100%; charged;\n")
    assert on_ac.ok is True

    on_batt = fly.on_ac_power("Now drawing from 'Battery Power'\n -InternalBattery-0 80%; discharging;\n")
    assert on_batt.ok is False

    desktop = fly.on_ac_power("Now drawing from 'AC Power'\n")
    assert desktop.ok is True


def test_idle_guard_parses_hid_idle_time():
    # 11 minutes idle, in nanoseconds
    eleven_minutes_ns = int(11 * 60 * 1e9)
    idle = fly.check_idle_guard(idle_seconds_value=eleven_minutes_ns / 1e9)
    assert idle.ok is True

    five_minutes_ns = int(5 * 60 * 1e9)
    busy = fly.check_idle_guard(idle_seconds_value=five_minutes_ns / 1e9)
    assert busy.ok is False


def test_idle_seconds_parses_real_ioreg_shape():
    sample = '''
    +-o Root  <class IORegistryEntry>
      "HIDIdleTime" = 723000000000
'''
    assert fly.idle_seconds(sample) == pytest.approx(723.0)


def test_display_asleep_guard_parses_current_power_state():
    awake = fly.display_asleep_or_locked('"CurrentPowerState" = 4\n')
    assert awake.ok is False  # ok means "asleep" here; state 4 is awake

    asleep = fly.display_asleep_or_locked('"CurrentPowerState" = 1\n')
    assert asleep.ok is True


def test_keyboard_activity_detected_when_idle_time_resets():
    assert fly.keyboard_activity_since(600.0, current_idle_seconds_value=2.0) is True
    assert fly.keyboard_activity_since(600.0, current_idle_seconds_value=650.0) is False


# --------------------------------------------------------- manifest write shape

def test_write_flown_measurement_matches_the_registry_schema(tmp_path):
    """The write must round-trip through the real parser -- not just this
    file's own code -- so a bad shape fails loudly, in this test, rather
    than the next time the registry loads."""
    from spacepilot.model_registry import parse_model

    src = Path("spacepilot/registry/models/edge0-8b-a1b.yaml")
    dst = tmp_path / "edge0-8b-a1b.yaml"
    dst.write_text(src.read_text())

    fly.write_flown_measurement(
        dst, "edge0-8b-a1b-preview-4bit",
        device="Apple M1 Max 32GB", backend="metal", metric="tokens_per_second",
        value=42.5, measured_on="2026-09-10", note="flown by tools/fly.py, dry run notwithstanding",
        working_set_bytes=1_200_000_000,
    )

    raw = yaml.safe_load(dst.read_text())
    model = parse_model(raw, "edge0-8b-a1b.yaml")
    variant = next(v for v in model.variants if v.id == "edge0-8b-a1b-preview-4bit")

    assert len(variant.speed) == 1
    assert variant.speed[0].value == 42.5
    assert variant.speed[0].source == "measured"
    assert variant.working_set.source == "measured"
    assert variant.working_set.value == 1_200_000_000
    # this variant is no longer "unflown" once the write lands
    assert fly.is_unflown(variant) is False


# ------------------------------------------------------------------- queue

def test_queue_stops_immediately_on_keyboard_activity(tmp_path):
    calls = []

    def fake_runner(model_id, **kwargs):
        calls.append(model_id)
        return fly.RunResult(model_id, "ok", [], "flown")

    outcomes = fly.fly_queue(
        max_minutes=240,
        while_idle=True,
        idle_check=lambda: fly.GuardResult(True, "idle 20.0 min"),
        display_check=lambda: fly.GuardResult(True, "display power state 1 (asleep/dimmed)"),
        keyboard_activity=lambda: True,  # activity from the very first check
        runner=fake_runner,
        log_dir=tmp_path,
    )
    assert outcomes == []
    assert calls == []


def test_queue_stops_when_not_idle():
    def fake_runner(model_id, **kwargs):
        raise AssertionError("must never run a job while the machine is not idle")

    outcomes = fly.fly_queue(
        max_minutes=240,
        while_idle=True,
        idle_check=lambda: fly.GuardResult(False, "idle 2.0 min (< 10 min required)"),
        display_check=lambda: fly.GuardResult(True, "display power state 1 (asleep/dimmed)"),
        runner=fake_runner,
        log_dir=Path("/tmp"),
    )
    assert outcomes == []


def test_queue_runs_within_time_budget_and_writes_the_flight_log(tmp_path):
    def fake_runner(model_id, **kwargs):
        return fly.RunResult(model_id, "ok", [], f"flown {model_id}")

    outcomes = fly.fly_queue(
        max_minutes=240,
        while_idle=True,
        idle_check=lambda: fly.GuardResult(True, "idle 20.0 min"),
        display_check=lambda: fly.GuardResult(True, "display power state 0 (asleep/dimmed)"),
        keyboard_activity=lambda: False,
        runner=fake_runner,
        log_dir=tmp_path,
    )
    assert len(outcomes) > 0
    log_path = tmp_path / "flight-log.jsonl"
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == len(outcomes)
    import json
    first = json.loads(lines[0])
    assert {"model_id", "start", "end", "outcome"} <= set(first)


def test_queue_stops_at_the_time_budget():
    calls = {"n": 0}

    def fake_runner(model_id, **kwargs):
        calls["n"] += 1
        return fly.RunResult(model_id, "ok", [], "flown")

    clock = {"t": 0.0}

    def fake_clock():
        return clock["t"]

    def fake_log(msg):
        pass

    # advance the fake clock past the budget after the first job
    real_runner = fake_runner

    def advancing_runner(model_id, **kwargs):
        clock["t"] += 999999  # blow the whole budget after one job
        return real_runner(model_id, **kwargs)

    outcomes = fly.fly_queue(
        max_minutes=1,
        while_idle=False,
        clock=fake_clock,
        runner=advancing_runner,
        log_dir=Path("/tmp"),
        log=fake_log,
    )
    assert calls["n"] == 1
    assert len(outcomes) == 1
