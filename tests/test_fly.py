"""tools/fly.py: plan ordering, runtime refusal, the dry-run flight of
Edge0-8B with no network, the idle/battery guards with faked probes, and the
manifest write shape validated against the real registry parser.

No test in this file downloads anything, runs `pmset`/`ioreg` for real
(every guard takes injected text), or leaves a git branch behind.
"""

import json
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
        disk_check=lambda: fly.GuardResult(True, "plenty free"),
        power_check=lambda: fly.GuardResult(True, "AC Power"),
        keyboard_activity=lambda: False,
        runner=fake_runner,
        log_dir=tmp_path,
    )
    assert len(outcomes) > 0
    log_path = tmp_path / "flight-log.jsonl"
    assert log_path.exists()
    import json
    lines = log_path.read_text().strip().splitlines()
    parsed = [json.loads(line) for line in lines]
    # Pre-flight install attempts (one per distinct not-installed runtime)
    # share the same log file, keyed by runtime_id instead of model_id --
    # see fly_queue's pre-flight phase.
    model_lines = [row for row in parsed if "model_id" in row]
    install_lines = [row for row in parsed if "runtime_id" in row]
    assert len(model_lines) == len(outcomes)
    assert len(lines) == len(model_lines) + len(install_lines)
    first = model_lines[0]
    assert {"model_id", "start", "end", "outcome"} <= set(first)
    if install_lines:
        assert {"runtime_id", "start", "end", "outcome", "detail", "duration_s"} <= set(install_lines[0])


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
        disk_check=lambda: fly.GuardResult(True, "plenty free"),
        power_check=lambda: fly.GuardResult(True, "AC Power"),
        clock=fake_clock,
        runner=advancing_runner,
        log_dir=Path("/tmp"),
        log=fake_log,
    )
    assert calls["n"] == 1
    assert len(outcomes) == 1


# ------------------------------------------------------------- power sampler
#
# `sudo` is not available in this environment (see the brief that added this
# section). Measured directly on this Mac, 2026-09-10: `powermetrics -n 1
# -i 1000 --samplers cpu_power` exits 0 but prints "powermetrics must be
# invoked as the superuser" and samples nothing -- so `check_powermetrics_
# unprivileged` has to read the *text*, not just the exit code, and the real
# fallback path is `ioreg -rn AppleSmartBattery`'s `InstantAmperage` /
# `Voltage` fields, which worked unprivileged in the same session (a
# two's-complement mA current times mV, giving instantaneous watts while on
# battery). Every test below injects fake subprocess text; none of them
# shells out for real.

def test_check_powermetrics_unprivileged_reads_the_superuser_message_as_not_ok():
    class FakeResult:
        returncode = 0
        stdout = "powermetrics must be invoked as the superuser\n"
        stderr = ""

    result = fly.check_powermetrics_unprivileged(runner=lambda cmd: FakeResult())
    assert result.ok is False
    assert "root" in result.reason or "superuser" in result.reason.lower() or "sudo" in result.reason.lower()


def test_check_powermetrics_unprivileged_accepts_a_real_sample():
    class FakeResult:
        returncode = 0
        stdout = "*** Sampled system activity ***\nCPU Power: 1234 mW\n"
        stderr = ""

    result = fly.check_powermetrics_unprivileged(runner=lambda cmd: FakeResult())
    assert result.ok is True


def test_check_powermetrics_unprivileged_handles_a_missing_binary():
    def raises(cmd):
        raise FileNotFoundError("no powermetrics")

    result = fly.check_powermetrics_unprivileged(runner=raises)
    assert result.ok is False


# Real `ioreg -rn AppleSmartBattery` output captured on this Mac, 2026-09-10,
# while discharging on battery: InstantAmperage as an unsigned 64-bit field
# carrying -1582 mA (18446744073709550034 == 2**64 - 1582) at 11441 mV.
REAL_IOREG_BATTERY_SAMPLE = '''
+-o AppleSmartBattery  <class AppleSmartBattery, id 0x100000aa9>
  | {
  |   "ExternalConnected" = No
  |   "Voltage" = 11441
  |   "InstantAmperage" = 18446744073709550034
  |   "Amperage" = 18446744073709550034
  | }
'''


def test_read_battery_instant_watts_parses_the_twos_complement_discharge_current():
    watts = fly.read_battery_instant_watts(REAL_IOREG_BATTERY_SAMPLE)
    # 1.582 A * 11.441 V ~= 18.10 W
    assert watts == pytest.approx(18.099, abs=0.01)


def test_read_battery_instant_watts_returns_none_when_fields_are_missing():
    assert fly.read_battery_instant_watts("no useful fields here\n") is None


def test_read_battery_instant_watts_handles_positive_charging_current():
    sample = '"Voltage" = 12000\n"InstantAmperage" = 500\n'
    assert fly.read_battery_instant_watts(sample) == pytest.approx(6.0)


def test_sample_power_falls_back_to_ioreg_when_powermetrics_needs_root():
    sample = fly.sample_power(
        powermetrics_check=lambda: fly.GuardResult(False, "needs root"),
        ioreg_output=REAL_IOREG_BATTERY_SAMPLE,
    )
    assert sample.available is True
    assert sample.source == fly.POWER_SOURCE_IOREG_BATTERY
    assert sample.watts == pytest.approx(18.099, abs=0.01)
    assert sample.limits  # non-empty: callers must be told this source's limits


def test_sample_power_reports_unavailable_when_neither_source_has_a_number():
    sample = fly.sample_power(
        powermetrics_check=lambda: fly.GuardResult(False, "needs root"),
        ioreg_output="no battery fields here\n",
    )
    assert sample.available is False
    assert sample.watts is None
    assert sample.source == fly.POWER_SOURCE_UNAVAILABLE


def test_energy_per_unit_computes_joules_per_unit():
    # 10 W for 5 s over 100 tokens = 0.5 J / token
    assert fly.energy_per_unit(10.0, 5.0, 100.0) == pytest.approx(0.5)


def test_energy_per_unit_rejects_zero_or_negative_units():
    with pytest.raises(ValueError):
        fly.energy_per_unit(10.0, 5.0, 0.0)
    with pytest.raises(ValueError):
        fly.energy_per_unit(10.0, 5.0, -1.0)


def test_role_energy_metric_covers_every_flight_plan_role():
    roles = {p.role for p in fly.FLIGHT_PLANS.values()}
    missing = roles - set(fly.ROLE_ENERGY_METRIC)
    assert not missing, f"roles with no energy metric mapping: {missing}"


def test_dry_run_reports_power_as_unmeasured():
    """A dry run stops before sampling anything -- the step log has to say
    so explicitly rather than silently omitting the power line."""
    result = fly.fly_run(
        "edge0-8b-a1b-preview-4bit",
        dry_run=True,
        downloader=fly.DryRunDownloader(),
        disk_check=lambda download_bytes: fly.GuardResult(True, "plenty free"),
        power_check=lambda: fly.GuardResult(True, "Now drawing from 'AC Power'"),
    )
    joined = "\n".join(result.steps)
    assert "unmeasured" in joined.lower()


def test_write_flown_measurement_carries_power_provenance(tmp_path):
    from spacepilot.model_registry import parse_model

    src = Path("spacepilot/registry/models/edge0-8b-a1b.yaml")
    dst = tmp_path / "edge0-8b-a1b.yaml"
    dst.write_text(src.read_text())

    fly.write_flown_measurement(
        dst, "edge0-8b-a1b-preview-4bit",
        device="this Mac", backend="metal", metric="joules_per_token",
        value=0.031, measured_on="2026-09-10", note="power sample",
        power_source=fly.POWER_SOURCE_IOREG_BATTERY, power_watts=18.1,
        power_limits="instantaneous battery discharge only",
    )

    raw = yaml.safe_load(dst.read_text())
    model = parse_model(raw, "edge0-8b-a1b.yaml")
    variant = next(v for v in model.variants if v.id == "edge0-8b-a1b-preview-4bit")
    entry = next(s for s in variant.speed if s.metric == "joules_per_token")
    assert entry.value == pytest.approx(0.031)
    assert entry.power_source == fly.POWER_SOURCE_IOREG_BATTERY
    assert entry.power_watts == pytest.approx(18.1)
    assert "battery" in entry.power_limits


# ------------------------------------------------------- queue: pre-flight installs
#
# `fly.py queue`'s pre-flight phase installs every planned model's missing
# runtime -- including the bitnet.cpp and PrismML source-tree builds -- under
# the same idle/AC-power/disk guards a flight itself checks, before flying
# anything. A failed install skips only the models that needed it and the
# night continues; a guard failure (idle, power, disk) stops the whole night,
# exactly like it always has. Every test here fakes both the installer and
# the guards -- none shells out, none touches the real registry.

def _fake_row(model_id: str, runtime_id: str, *, installed: bool, role="executor",
              backend="metal", download_bytes=1_000_000):
    """A minimal fake PlanRow/Variant pair, just enough for plan_rows()-shaped
    code to iterate without touching the real registry or spawning a real
    runtime check."""
    from types import SimpleNamespace

    variant = SimpleNamespace(
        id=model_id, model_id=model_id,
        download=SimpleNamespace(value=download_bytes),
        working_set=SimpleNamespace(value=download_bytes, source="unmeasured"),
        speed=[], backends=[backend], is_pinned=True, revision="deadbeef" * 5,
        repo="fake/repo", files=None,
    )
    plan = fly.FlightPlan(model_id, role, runtime_id, "text")
    runtime_status = fly.RuntimeStatus(installed, None if installed else
                                        f"spacepilot runtimes install {runtime_id}",
                                        "installed" if installed else "not installed")
    return fly.PlanRow(variant, plan, runtime_status)


def test_run_runtime_install_dry_run_logs_the_command_and_touches_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(fly.subprocess, "run",
                         lambda *a, **kw: (_ for _ in ()).throw(
                             AssertionError("dry-run must never shell out")))
    runtime = fly.rt.runtimes()["mlx-lm"]
    result = fly.run_runtime_install(runtime, dry_run=True, log=calls.append)
    assert result.ok
    assert result.duration_s == 0.0
    assert any("dry-run" in c and runtime.id in c for c in calls)


def test_run_runtime_install_wraps_the_real_command_with_nice_and_bounded_jobs(monkeypatch):
    runtime = fly.rt.runtimes()["bitnet-cpp"]
    seen = {}

    def fake_runner(cmd, **kw):
        seen["cmd"] = cmd
        seen["env"] = kw.get("env")
        return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def fake_check(r):
        return fly.rt.Status(r.id, True, "1.0.0")

    result = fly.run_runtime_install(
        runtime, dry_run=False, jobs=3, command_runner=fake_runner,
        check_fn=fake_check, log=lambda *_: None,
    )
    assert result.ok
    assert seen["cmd"][:3] == ["nice", "-n", "19"]
    assert seen["env"]["CMAKE_BUILD_PARALLEL_LEVEL"] == "3"
    assert seen["env"]["MAKEFLAGS"] == "-j3"


def test_run_runtime_install_reports_the_log_tail_on_failure(monkeypatch):
    runtime = fly.rt.runtimes()["llama-cpp-prism"]

    def fake_runner(cmd, **kw):
        return type("P", (), {
            "returncode": 1, "stdout": "line1\nline2\n",
            "stderr": "cmake: configure error\n",
        })()

    result = fly.run_runtime_install(
        runtime, dry_run=False, command_runner=fake_runner, log=lambda *_: None,
    )
    assert not result.ok
    assert "configure error" in result.detail


def test_run_runtime_install_surfaces_the_missing_gguf_message_verbatim(monkeypatch):
    """bitnet-cpp's install script now fails fast (exit 2) with a one-line
    stderr message naming the missing ggml-model-i2_s.gguf and the fly
    command that fetches it, instead of failing deep inside a CMake build
    with a confusing setup_env error.

    `run_runtime_install`'s own dry-run mode (`dry_run=True`) never invokes
    a command at all -- it only logs the argv it would run (see
    `test_run_runtime_install_dry_run_logs_the_command_and_touches_nothing`
    above) -- so there is no way to observe a script's stderr without
    actually running something. This test instead follows the shape of
    `test_run_runtime_install_reports_the_log_tail_on_failure` immediately
    above: a fake `command_runner` stands in for the real subprocess call
    (dry_run=False, but nothing real executes -- the fake never shells out),
    and asserts the guard's exact message survives into `result.detail`
    rather than being flattened into a generic 'install failed' string."""
    runtime = fly.rt.runtimes()["bitnet-cpp"]
    guard_message = (
        "install-bitnet-cpp.sh: ggml-model-i2_s.gguf not found in "
        "<model-dir> -- fetch it first: tools/fly.py run "
        "bitnet-b1-58-2b4t-gguf-i2s\n"
    )

    def fake_runner(cmd, **kw):
        return type("P", (), {
            "returncode": 2, "stdout": "", "stderr": guard_message,
        })()

    result = fly.run_runtime_install(
        runtime, dry_run=False, command_runner=fake_runner, log=lambda *_: None,
    )
    assert not result.ok
    assert "ggml-model-i2_s.gguf" in result.detail
    assert "fly.py run bitnet-b1-58-2b4t-gguf-i2s" in result.detail
    assert result.detail != "install exited 2"


def test_run_runtime_install_distrusts_a_zero_exit_that_still_fails_check(monkeypatch):
    """A script that exits 0 having built the wrong thing is not installed
    either -- the same honesty bar spacepilot.runtimes.install() holds pip
    to."""
    runtime = fly.rt.runtimes()["bitnet-cpp"]

    def fake_runner(cmd, **kw):
        return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def fake_check(r):
        return fly.rt.Status(r.id, False, None, "bitnet-cli not found on PATH")

    result = fly.run_runtime_install(
        runtime, dry_run=False, command_runner=fake_runner,
        check_fn=fake_check, log=lambda *_: None,
    )
    assert not result.ok
    assert "not found on PATH" in result.detail


def test_queue_preflight_installs_each_missing_runtime_once_before_flights(tmp_path):
    rows = [
        _fake_row("model-a-1", "shared-rt", installed=False, download_bytes=10),
        _fake_row("model-b-1", "shared-rt", installed=False, download_bytes=20),
        _fake_row("model-c-1", "other-rt", installed=True, download_bytes=30),
    ]
    install_calls = []

    def fake_install_runner(runtime, *, dry_run, jobs, log):
        install_calls.append(runtime.id)
        return fly.RuntimeInstallResult(runtime.id, True, "installed 1.0.0", 2.5)

    flown = []

    def fake_runner(model_id, **kwargs):
        flown.append(model_id)
        return fly.RunResult(model_id, "ok", [], "flown")

    class FakeReg:
        pass

    import fly as fly_mod
    fake_rt_registry = {"shared-rt": fly_mod.rt.runtimes()["bitnet-cpp"]}
    orig_runtimes = fly_mod.rt.runtimes
    orig_plan_rows = fly_mod.plan_rows
    fly_mod.rt.runtimes = lambda: fake_rt_registry
    fly_mod.plan_rows = lambda reg=None: rows
    try:
        outcomes = fly.fly_queue(
            max_minutes=240, while_idle=True, dry_run=False,
            idle_check=lambda: fly.GuardResult(True, "idle"),
            display_check=lambda: fly.GuardResult(True, "asleep"),
            disk_check=lambda: fly.GuardResult(True, "plenty free"),
            power_check=lambda: fly.GuardResult(True, "AC Power"),
            keyboard_activity=lambda: False,
            install_runner=fake_install_runner,
            runner=fake_runner,
            log_dir=tmp_path,
        )
    finally:
        fly_mod.rt.runtimes = orig_runtimes
        fly_mod.plan_rows = orig_plan_rows

    # installed exactly once, not once per model that needs it
    assert install_calls == [fake_rt_registry["shared-rt"].id]
    assert flown == ["model-a-1", "model-b-1", "model-c-1"]
    assert [o.outcome for o in outcomes] == ["ok", "ok", "ok"]

    log_lines = [json.loads(l) for l in (tmp_path / "flight-log.jsonl").read_text().splitlines()]
    install_entries = [l for l in log_lines if l.get("runtime_id") == "shared-rt"]
    assert len(install_entries) == 1
    assert install_entries[0]["outcome"] == "ok"
    assert install_entries[0]["duration_s"] == 2.5


def test_queue_preflight_dry_run_never_calls_a_real_installer(tmp_path):
    rows = [_fake_row("model-a-1", "shared-rt", installed=False)]

    def real_install_runner_would_explode(*a, **kw):
        raise AssertionError("dry-run must never invoke a real install path")

    import fly as fly_mod
    orig_runtimes = fly_mod.rt.runtimes
    orig_plan_rows = fly_mod.plan_rows
    fake_runtime = fly_mod.rt.runtimes()["bitnet-cpp"]
    fly_mod.rt.runtimes = lambda: {"shared-rt": fake_runtime}
    fly_mod.plan_rows = lambda reg=None: rows
    logged = []
    try:
        outcomes = fly.fly_queue(
            max_minutes=240, while_idle=True, dry_run=True,
            idle_check=lambda: fly.GuardResult(True, "idle"),
            display_check=lambda: fly.GuardResult(True, "asleep"),
            disk_check=lambda: fly.GuardResult(True, "plenty free"),
            power_check=lambda: fly.GuardResult(True, "AC Power"),
            keyboard_activity=lambda: False,
            runner=lambda model_id, **kw: fly.RunResult(model_id, "dry-run", [], ""),
            log=logged.append,
            log_dir=tmp_path,
        )
    finally:
        fly_mod.rt.runtimes = orig_runtimes
        fly_mod.plan_rows = orig_plan_rows

    assert any("[dry-run] would install" in l and fake_runtime.id in l for l in logged)
    log_lines = [json.loads(l) for l in (tmp_path / "flight-log.jsonl").read_text().splitlines()]
    install_entries = [l for l in log_lines if l.get("runtime_id") == "shared-rt"]
    assert install_entries[0]["outcome"] == "dry-run"


def test_queue_preflight_failed_install_skips_only_its_own_models_and_continues(tmp_path):
    rows = [
        _fake_row("model-a-1", "broken-rt", installed=False),
        _fake_row("model-b-1", "broken-rt", installed=False),
        _fake_row("model-c-1", "fine-rt", installed=True),
    ]

    def fake_install_runner(runtime, *, dry_run, jobs, log):
        return fly.RuntimeInstallResult(runtime.id, False, "cmake: configure error", 1.2)

    flown = []

    def fake_runner(model_id, **kwargs):
        flown.append(model_id)
        return fly.RunResult(model_id, "ok", [], "flown")

    import fly as fly_mod
    orig_runtimes = fly_mod.rt.runtimes
    orig_plan_rows = fly_mod.plan_rows
    fake_broken_runtime = fly_mod.rt.runtimes()["llama-cpp-prism"]
    fly_mod.rt.runtimes = lambda: {"broken-rt": fake_broken_runtime}
    fly_mod.plan_rows = lambda reg=None: rows
    try:
        outcomes = fly.fly_queue(
            max_minutes=240, while_idle=True, dry_run=False,
            idle_check=lambda: fly.GuardResult(True, "idle"),
            display_check=lambda: fly.GuardResult(True, "asleep"),
            disk_check=lambda: fly.GuardResult(True, "plenty free"),
            power_check=lambda: fly.GuardResult(True, "AC Power"),
            keyboard_activity=lambda: False,
            install_runner=fake_install_runner,
            runner=fake_runner,
            log_dir=tmp_path,
        )
    finally:
        fly_mod.rt.runtimes = orig_runtimes
        fly_mod.plan_rows = orig_plan_rows

    # the night never aborts -- model-c-1 (a different, working runtime)
    # still flies even though broken-rt's install failed.
    assert flown == ["model-c-1"]
    by_id = {o.model_id: o for o in outcomes}
    assert by_id["model-a-1"].outcome == "skipped"
    assert "skipped: install failed" in by_id["model-a-1"].detail
    assert "configure error" in by_id["model-a-1"].detail
    assert by_id["model-b-1"].outcome == "skipped"
    assert by_id["model-c-1"].outcome == "ok"


def test_queue_preflight_stops_the_whole_night_on_a_guard_failure_not_just_a_skip(tmp_path):
    """A guard failure (idle/power/disk) is not the same thing as an install
    failure -- it stops everything, the same as it always has for a flight,
    rather than being scoped to one runtime's models."""
    rows = [_fake_row("model-a-1", "shared-rt", installed=False)]

    def must_not_run(*a, **kw):
        raise AssertionError("must never install or fly while a guard fails")

    import fly as fly_mod
    orig_runtimes = fly_mod.rt.runtimes
    orig_plan_rows = fly_mod.plan_rows
    fake_guard_runtime = fly_mod.rt.runtimes()["bitnet-cpp"]
    fly_mod.rt.runtimes = lambda: {"shared-rt": fake_guard_runtime}
    fly_mod.plan_rows = lambda reg=None: rows
    try:
        outcomes = fly.fly_queue(
            max_minutes=240, while_idle=True, dry_run=False,
            idle_check=lambda: fly.GuardResult(False, "idle 2.0 min (< 10 min required)"),
            display_check=lambda: fly.GuardResult(True, "asleep"),
            install_runner=must_not_run,
            runner=must_not_run,
            log_dir=tmp_path,
        )
    finally:
        fly_mod.rt.runtimes = orig_runtimes
        fly_mod.plan_rows = orig_plan_rows

    assert outcomes == []


# ------------------------------------------------------- flight-plan coverage

def _registry_runtime_runs():
    """(runtime_yaml_id, model_id) for every model listed under `runs:` in
    every spacepilot/registry/runtimes/*.yaml file."""
    pairs = []
    for yaml_path in sorted(fly.rt.RUNTIME_DIR.glob("*.yaml")):
        raw = yaml.safe_load(yaml_path.read_text())
        runtime_id = raw["id"]
        for model_id in raw.get("runs") or []:
            pairs.append((runtime_id, model_id))
    return pairs


# Registry runtime `runs:` entries confirmed unmapped in tools/fly.py's
# FLIGHT_PLANS as of this test's introduction (2026-09-12). None of these is
# invented here -- each is a real gap this test found. Do not add a mapping
# to this set to make it pass; either wire the model in FLIGHT_PLANS and
# remove it from here, or leave it and it stays visibly BLOCKED via
# fly.py's own runtime_status()/plan() reporting.
KNOWN_UNMAPPED = {
    ("diffusers", "wan-2-1"),
    ("diffusers", "wan-2-2"),
    ("diffusers", "ltx-video"),
    ("diffusers", "flux"),
    ("kokoro-onnx", "kokoro"),
    ("llama-cpp", "deepseek-r1-distill-qwen"),
    ("llama-cpp", "qwen2-5-vl"),
    ("mflux", "flux"),
    ("mflux", "qwen-image"),
    ("mflux", "z-image"),
    ("mflux", "fibo"),
    ("mflux", "ernie-image"),
    ("mflux", "ideogram"),
    ("mflux", "seedvr2"),
    ("mflux", "boogu"),
    ("mflux", "lens"),
    ("mflux", "flux2-klein"),
    ("mlx-audio", "kokoro"),
    ("mlx-lm", "qwen3-8"),
    ("mlx-lm", "qwen3-embedding"),
    ("mlx-video", "wan-2-1"),
    ("mlx-video", "wan-2-2"),
    ("mlx-video", "ltx-video"),
    ("whisper-cpp", "whisper"),
}


@pytest.mark.parametrize("runtime_id,model_id", _registry_runtime_runs())
def test_every_registry_runtime_run_is_a_mapped_flight_plan(runtime_id, model_id):
    """Every model a runtime recipe's `runs:` list names must have a
    FLIGHT_PLANS entry that points back at that same runtime -- otherwise
    `fly.py plan` prints it as "role unmapped" forever, silently, even
    though a runtime already exists to fly it (ternary-bonsai-8b via
    llama-cpp-prism was exactly this bug)."""
    if (runtime_id, model_id) in KNOWN_UNMAPPED:
        pytest.skip(f"{model_id}: known unmapped in FLIGHT_PLANS, see KNOWN_UNMAPPED")
    assert model_id in fly.FLIGHT_PLANS, (
        f"{model_id} is listed under runs: in {runtime_id}.yaml but has no "
        f"FLIGHT_PLANS entry in tools/fly.py")
    plan = fly.FLIGHT_PLANS[model_id]
    assert plan.runtime_id == runtime_id, (
        f"{model_id}'s FLIGHT_PLANS entry points at runtime_id "
        f"{plan.runtime_id!r}, but it is registered under runs: in "
        f"{runtime_id}.yaml")


def test_every_mapped_runtime_id_names_a_runtime_that_exists():
    """The reverse direction: every FLIGHT_PLANS entry with a real
    runtime_id must name a runtime recipe that actually exists in
    spacepilot/registry/runtimes/ -- a typo'd or removed runtime_id would
    otherwise fail silently at `runtime_status()` time instead of here."""
    known_runtime_ids = {p.stem for p in fly.rt.RUNTIME_DIR.glob("*.yaml")}
    # every yaml's own `id:` field should also match its filename stem
    for yaml_path in sorted(fly.rt.RUNTIME_DIR.glob("*.yaml")):
        raw = yaml.safe_load(yaml_path.read_text())
        assert raw["id"] == yaml_path.stem
    for model_id, plan in fly.FLIGHT_PLANS.items():
        if plan.runtime_id is None:
            continue
        assert plan.runtime_id in known_runtime_ids, (
            f"{model_id}'s FLIGHT_PLANS entry names runtime_id "
            f"{plan.runtime_id!r}, which has no "
            f"spacepilot/registry/runtimes/{plan.runtime_id}.yaml")
