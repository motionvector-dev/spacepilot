# PR #9 Review: Fix ffmpeg 6.1 Apple multichannel sources

**Branch:** `ffmpeg-error` → `staging` · **3 commits, 3 files** · +85 / -6

---

## Summary

ffmpeg 6.1.1 (shipped in Ubuntu 24.04) can't parse Apple's multichannel `chan` atom in 5.1 surround files — it fails the *entire* header read, making the video unreadable alongside the audio. This took down **four prod streamed jobs** on 2026-08-17 (all 1080p 5.1 concert masters). The fix has two halves:

1. **Dockerfile(s):** install ffmpeg 7.1 so the probe succeeds
2. **Orchestrator:** stop wasting retries on input-caused failures, and stop losing pod error messages

---

## File-by-file

### 1. `Dockerfile` (+28 / -1)

Installs a **static ffmpeg 7.1 binary** from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) into `/usr/local/bin/`, ahead of the apt ffmpeg on `PATH`.

**Why static + keep apt?** torio/torchaudio `dlopen`s versioned sonames (`libavformat.so.60`). A system-wide upgrade to 7.x (`.so.61`) would break the split path's cuvid decode + NVENC encode. Smart tradeoff.

**Build-time assertions:**
- `grep -q "n7.1"` — confirms version
- `ldd ... | grep -qv libavformat` — confirms it's truly static (not accidentally linking the apt `.so.60`)

> [!TIP]
> **Looks good.** The `xz-utils` addition for `tar -xJf` is correct. Clean separation between CLI binary and shared libs.

### 2. `Dockerfile.cpu` (+16 / -0)

Doesn't install a new binary — the `python:3.11-slim` (Debian trixie) base already ships ffmpeg ≥ 7.1 from apt. Instead adds a **build-time version assertion** that fails the build if a future base image ever regresses below 7.1.

> [!TIP]
> **Looks good.** Defensive and zero-cost at runtime. The `sort -V` semver check is portable enough for Debian/Ubuntu.

### 3. `orchestrator-service/orchestrate_job.py` (+41 / -5)

Three changes, all related:

#### a) `TERMINAL_FAILURE_REASONS` + `TerminalStageError`

New constant `{"unreadable_source"}` and exception class. When `wait_done()` sees the pod stamped a terminal `failure_reason` in Mongo, it raises `TerminalStageError` instead of generic `RuntimeError`.

> [!NOTE]
> The comment explains why these are bare strings (not an import from `pipeline_core`): the orchestrator image has no torch, so Mongo is the contract boundary. Good.

#### b) Error propagation in `wait_done()`

The Mongo `find_one` projection now includes `"error": 1, "failure_reason": 1`. On `status == "failed"`:

```python
pod_err = (doc.get("error") or "").strip()
detail = f": {pod_err}" if pod_err else ""
reason = doc.get("failure_reason")
if reason in TERMINAL_FAILURE_REASONS:
    raise TerminalStageError(f"stage {stage} failed terminally [{reason}]{detail}")
raise RuntimeError(f"stage {stage}: job marked failed in Mongo{detail}")
```

> [!IMPORTANT]
> **This is the highest-value change in the PR.** Previously every pod crash surfaced as the generic `"job marked failed in Mongo"` — the comment says that's cost "two multi-hour investigations" already. Now the pod's own error text is carried out.

#### c) Retry-skip for terminal errors

`TerminalStageError` is caught *before* the generic `except Exception` in the retry loop → pod terminated, then re-raised immediately (no retry). In the outer handler, `isinstance(e, TerminalStageError)` extracts the reason from the `[reason]` tag in the message via `next()` generator.

---

## Issues / Nits

### ⚠️ Medium

| # | Location | Issue |
|---|----------|-------|
| 1 | `orchestrate_job.py:358` | The `next()` reason extraction parses `[unreadable_source]` from `msg` via string matching. If someone adds a terminal reason containing regex-special chars or square brackets, this silently falls through to `"processing_failed"`. Fine for now with one reason, but worth a `# NOTE:` if the set grows. |
| 2 | Commit history | `a0e4b05 Idk` — consider squashing or amending the message before merge. |

### 💡 Nit

| # | Location | Issue |
|---|----------|-------|
| 3 | `Dockerfile:36-37` | The `FFMPEG_BUILD` and `FFMPEG_DIR` ARGs are pinned to a specific autobuild. If you ever need to bump, you have to edit two coupled strings. Could use a single `FFMPEG_VERSION` ARG, but honestly the explicitness is fine for an infrequent change. |
| 4 | `Dockerfile:45` | `ldd /usr/local/bin/ffprobe | grep -qv libavformat` — on a truly static binary, `ldd` prints `not a dynamic executable` and exits 1, which would fail the `grep -qv`. Worth verifying this passes in CI. If the BtbN build is *statically linked but still ELF* (no dynamic loader needed), `ldd` may behave differently. A safer check might be `! ldd /usr/local/bin/ffprobe 2>&1 | grep -q libavformat`. |

---

## Verdict

> **Ship it** (after squashing the "Idk" commit message). The Dockerfile approach is well-reasoned — static binary overlay is the right call given the torchaudio `.so` constraint. The orchestrator changes are overdue quality-of-life: terminal failure reasons prevent wasted retries on bad inputs, and carrying the pod error text forward will save hours of debugging.
