"""Gate 3 for executor-role flights: `tools/fly.py` materialises
benchmarks/l2r/ from the engine repo (motionvector-dev/motionvector's
mvec-engine) via `git archive`, never a worktree, and logs the exact command
it would run against the model under test.

A previous lane reported Gate 3 "missing" because it looked at the local
mvec-engine checkout, which sits on a feature branch -- it exists on the
engine's own `origin/main`. `--engine-ref` (default `origin/main`) is what
fly.py actually pulls from, and every test here fakes the engine repo rather
than touching the real one, the same way test_fly.py fakes the downloader.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import fly  # noqa: E402


# ------------------------------------------------------------- dry-run gate3

def test_dry_run_of_an_executor_logs_the_archive_step_and_the_gate3_command():
    """edge0-35b-a3b-preview-4bit is role=executor, needs_gate3=True (see
    tools/fly.py's FLIGHT_PLANS) -- its dry run must show both the archive
    it would run and the exact Gate 3 command, without touching git."""
    result = fly.fly_run(
        "edge0-35b-a3b-preview-4bit",
        dry_run=True,
        disk_check=lambda download_bytes: fly.GuardResult(True, "plenty free"),
        power_check=lambda: fly.GuardResult(True, "on AC"),
        engine_ref="origin/main",
    )
    assert result.outcome == "dry-run"
    joined = "\n".join(result.steps)
    assert "[dry-run] would archive benchmarks/l2r from mvec-engine@origin/main" in joined
    assert "git -C" in joined and "archive origin/main benchmarks/l2r" in joined
    assert "tar -x -C" in joined
    assert "gate3 command (cwd=" in joined
    assert "gate3_semantic.py --model edge0-35b-a3b-preview-4bit" in joined
    assert "MVEC_BIN=" in joined


def test_dry_run_of_a_transducer_never_mentions_gate3():
    """edge0-8b-a1b-preview-4bit is role=transducer, needs_gate3=False --
    only executors get Gate 3, per FlightPlan.needs_gate3."""
    result = fly.fly_run(
        "edge0-8b-a1b-preview-4bit",
        dry_run=True,
        disk_check=lambda download_bytes: fly.GuardResult(True, "plenty free"),
        power_check=lambda: fly.GuardResult(True, "on AC"),
    )
    assert result.outcome == "dry-run"
    joined = "\n".join(result.steps)
    assert "gate3" not in joined.lower()


def test_dry_run_never_shells_out_to_git_for_gate3():
    calls = []
    real_run = subprocess.run

    def spy(argv, *a, **kw):
        calls.append(argv)
        return real_run(argv, *a, **kw)

    import tools.fly as fly_mod  # same module object as `fly`
    orig = fly_mod.subprocess.run
    fly_mod.subprocess.run = spy
    try:
        result = fly.fly_run(
            "edge0-35b-a3b-preview-4bit",
            dry_run=True,
            disk_check=lambda download_bytes: fly.GuardResult(True, "plenty free"),
            power_check=lambda: fly.GuardResult(True, "on AC"),
        )
    finally:
        fly_mod.subprocess.run = orig
    assert result.outcome == "dry-run"
    assert not any(c and c[0] == "git" and "archive" in c for c in calls), \
        "dry-run must never actually shell out to `git archive`"


def test_engine_ref_defaults_to_origin_main():
    assert fly.DEFAULT_ENGINE_REF == "origin/main"


def test_custom_engine_ref_is_reflected_in_the_dry_run_log():
    result = fly.fly_run(
        "edge0-35b-a3b-preview-4bit",
        dry_run=True,
        disk_check=lambda download_bytes: fly.GuardResult(True, "plenty free"),
        power_check=lambda: fly.GuardResult(True, "on AC"),
        engine_ref="a004338a",
    )
    joined = "\n".join(result.steps)
    assert "mvec-engine@a004338a" in joined
    assert "archive a004338a benchmarks/l2r" in joined


# --------------------------------------------------------- resolve_mvec_bin

def test_resolve_mvec_bin_prefers_the_first_existing_candidate(tmp_path):
    missing = tmp_path / "does-not-exist"
    present = tmp_path / "mvec"
    present.write_text("#!/bin/sh\n")
    fallback = tmp_path / "fallback" / "mvec"
    fallback.parent.mkdir()
    fallback.write_text("#!/bin/sh\n")

    found = fly.resolve_mvec_bin([missing, present, fallback])
    assert found == present


def test_resolve_mvec_bin_falls_through_to_the_second_candidate(tmp_path):
    missing = tmp_path / "does-not-exist"
    fallback = tmp_path / "fallback" / "mvec"
    fallback.parent.mkdir()
    fallback.write_text("#!/bin/sh\n")

    found = fly.resolve_mvec_bin([missing, fallback])
    assert found == fallback


def test_resolve_mvec_bin_returns_none_when_nothing_is_found(tmp_path):
    found = fly.resolve_mvec_bin([tmp_path / "a", tmp_path / "b"])
    assert found is None


# ------------------------------------------------------ gate3_command shape

def test_gate3_command_runs_from_inside_the_extracted_l2r_dir(tmp_path):
    l2r_dir = tmp_path / "benchmarks" / "l2r"
    l2r_dir.mkdir(parents=True)
    cmd = fly.gate3_command(l2r_dir, "edge0-35b-a3b-preview-4bit", python_bin="/tmp/py")
    assert cmd[0] == "/tmp/py"
    assert cmd[1] == str(l2r_dir / "gate3_semantic.py")
    assert cmd[-2:] == ["--model", "edge0-35b-a3b-preview-4bit"]


# --------------------------------------------------- git archive extraction

def _make_fake_engine_repo(tmp_path: Path) -> Path:
    """A tiny real git repo standing in for mvec-engine, with a
    benchmarks/l2r/ subtree on `main` -- enough for `git archive` to pull
    for real, without touching the actual mvec-engine checkout."""
    repo = tmp_path / "fake-mvec-engine"
    repo.mkdir()
    l2r = repo / "benchmarks" / "l2r"
    l2r.mkdir(parents=True)
    (l2r / "gate3_semantic.py").write_text("print('gate3 stub')\n")
    (l2r / "fixture.py").write_text("def get_gate3_fixture_doc(): return {}\n")
    (repo / "README.md").write_text("fake engine repo\n")

    run = lambda *a: subprocess.run(a, cwd=str(repo), check=True,
                                     capture_output=True, text=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.email", "test@example.invalid")
    run("git", "config", "user.name", "Test")
    run("git", "add", ".")
    run("git", "commit", "-q", "-m", "initial")
    return repo


def test_git_archive_extractor_pulls_benchmarks_l2r_for_real(tmp_path):
    engine_repo = _make_fake_engine_repo(tmp_path)
    dest = tmp_path / "scratch"

    extractor = fly.GitArchiveGate3Extractor(log=lambda *_: None)
    l2r_dir = extractor.extract(engine_repo, "main", dest)

    assert l2r_dir == dest / "benchmarks" / "l2r"
    assert (l2r_dir / "gate3_semantic.py").read_text() == "print('gate3 stub')\n"
    assert (l2r_dir / "fixture.py").is_file()
    # only the requested subtree was extracted, not the whole repo
    assert not (dest / "README.md").exists()


def test_git_archive_extractor_reads_a_pinned_sha_not_just_a_branch_name(tmp_path):
    engine_repo = _make_fake_engine_repo(tmp_path)
    sha = subprocess.run(["git", "-C", str(engine_repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    dest = tmp_path / "scratch"

    extractor = fly.GitArchiveGate3Extractor(log=lambda *_: None)
    l2r_dir = extractor.extract(engine_repo, sha, dest)
    assert (l2r_dir / "gate3_semantic.py").is_file()


def test_git_archive_extractor_raises_when_the_ref_has_no_benchmarks_l2r(tmp_path):
    """A ref that does not carry benchmarks/l2r (e.g. a stale local branch
    predating it) must fail loudly, not silently extract nothing and let
    the caller run gate3_semantic.py against an empty directory."""
    repo = tmp_path / "empty-engine"
    repo.mkdir()
    (repo / "README.md").write_text("no benchmarks here\n")
    run = lambda *a: subprocess.run(a, cwd=str(repo), check=True,
                                     capture_output=True, text=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.email", "test@example.invalid")
    run("git", "config", "user.name", "Test")
    run("git", "add", ".")
    run("git", "commit", "-q", "-m", "initial")

    dest = tmp_path / "scratch"
    extractor = fly.GitArchiveGate3Extractor(log=lambda *_: None)
    with pytest.raises(RuntimeError, match="benchmarks/l2r"):
        extractor.extract(repo, "main", dest)


def test_dry_run_extractor_touches_no_filesystem(tmp_path):
    engine_repo = tmp_path / "not-created"
    dest = tmp_path / "also-not-created"
    extractor = fly.DryRunGate3Extractor(log=lambda *_: None)
    l2r_dir = extractor.extract(engine_repo, "origin/main", dest)
    assert l2r_dir == dest / "benchmarks" / "l2r"
    assert not dest.exists()
