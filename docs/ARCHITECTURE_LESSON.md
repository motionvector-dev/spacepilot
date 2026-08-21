# System Architecture Lesson: Katana Upscaler-GPU

Alright, listen up junior clankers. Today we're breaking down the architecture of the Katana `upscaler-gpu` repository. We are going to look at how we process massive video files at scale, how our orchestrator works, and why PR #9 was a critical lesson in distributed systems design.

---

## 1. The Big Picture: Control Plane vs. Data Plane

In any distributed processing system, you must separate your **Control Plane** (the brains, the state) from your **Data Plane** (the heavy lifting, the muscle).

In our repo, the Orchestrator is the control plane, and the ephemeral Modal/Runpod instances are the data plane.

```text
                        +----------------------+
                        |   Katana Frontend    |
                        +----------+-----------+
                                   |
                                (1) Job Request
                                   v
+-------------------------------------------------------------------------+
|                          CONTROL PLANE                                  |
|                                                                         |
|  +--------------------+      (2) Writes State      +-----------------+  |
|  |                    | -------------------------> |                 |  |
|  | Orchestrator Pod   |                            |   MongoDB       |  |
|  | (orchestrate_job)  | <------------------------- | (Job Document)  |  |
|  |                    |      (3) Polls State       +-----------------+  |
|  +---------+----------+                                     ^           |
+------------|------------------------------------------------|-----------+
             |                                                |
             | (4) Spawns ephemeral pods                      | (5) Updates progress/status
             v                                                |
+-------------------------------------------------------------|-----------+
|                           DATA PLANE                        |           |
|                                                             |           |
|  +-----------------+    +-----------------+    +------------|----+      |
|  | Preprocess Pod  | -> |   GPU Pod(s)    | -> | Postprocess Pod |      |
|  | (CPU/ffmpeg)    |    | (TensorRT/CUDA) |    | (CPU/ffmpeg)    |      |
|  +-----------------+    +-----------------+    +-----------------+      |
|                                                                         |
+-------------------------------------------------------------------------+
```

### Why do it this way?
1. **Cost:** GPUs are expensive. We only spin up the `GPU Pod` exactly when we need it, and tear it down immediately after. The `Orchestrator` runs on a cheap CPU instance.
2. **Resilience:** If a GPU pod crashes due to an Out-Of-Memory (OOM) error, the Orchestrator is completely isolated and safe. It just sees the pod die, spins up a new one, and tries again.

---

## 2. The Dependency Hell: ffmpeg vs. PyTorch

Our Data Plane relies on two massive dependencies: **ffmpeg** (for reading/writing video) and **PyTorch/torchaudio** (for running the AI models). 

This creates a brutal dependency conflict, which was the root cause of PR #9.

```text
                   THE DEPENDENCY CONFLICT
                   =======================

[ OS: Ubuntu 24.04 ]
       |
       |-- apt install ffmpeg -----> Gives us FFmpeg 6.1 (Shared Libs)
       |
       |-- pip install torchaudio -> Demands specific libavformat.so.60
                                     (Tied exactly to FFmpeg 6.1!)
```

**The Problem:** FFmpeg 6.1 has a bug. It completely crashes when trying to read Apple 5.1 multichannel audio files. We *must* upgrade to FFmpeg 7.1 to process these files. 

**The Naive Fix:** Run `apt install ffmpeg=7.1`.
**Why it fails:** FFmpeg 7.1 updates the shared libraries to `libavformat.so.61`. Torchaudio wakes up, looks for `so.60`, doesn't find it, and crashes the entire GPU pipeline.

**The Architect's Fix (PR #9):**
Instead of touching the OS-level shared libraries, we download a **statically compiled** version of the FFmpeg CLI binary and place it in `/usr/local/bin/`.

```text
[ /usr/lib/ ]
   ├── libavformat.so.60  <--- Torchaudio happily uses this (v6.1)
   └── libavcodec.so.60

[ /usr/local/bin/ ]
   └── ffmpeg (STATIC)    <--- Our Python subprocesses use this (v7.1)
                               It has no shared dependencies!
```
*Lesson: When integrating massive C++ libraries in Python, statically compiled binaries are your ultimate escape hatch.*

---

## 3. The Orchestrator Retry Loop and Terminal Errors

Now, let's look at how the Orchestrator handles failures. Before PR #9, the orchestrator had a simple rule: **"If a pod fails, retry up to 3 times."**

This is a great rule for *transient* failures (e.g., "AWS had a network blip", "No GPUs available"). It is a **terrible** rule for *deterministic* failures.

### The old flow (The "Insanity" Loop):
```text
(Attempt 1) Orchestrator spawns Pod -> Pod downloads 10GB video -> FFmpeg crashes -> Pod dies
(Attempt 2) Orchestrator spawns Pod -> Pod downloads 10GB video -> FFmpeg crashes -> Pod dies
(Attempt 3) Orchestrator spawns Pod -> Pod downloads 10GB video -> FFmpeg crashes -> Pod dies
[Orchestrator gives up, marks job failed]
```
This wasted hours of compute time and bandwidth because a bad input file will *always* be a bad input file. 

### The new flow (Terminal Errors):
PR #9 introduced the concept of `TERMINAL_FAILURE_REASONS`. The Data Plane now inspects *why* it crashed, and writes that reason to the Control Plane (Mongo).

```text
+-----------------------+                    +-------------------------+
|      DATA PLANE       |                    |      CONTROL PLANE      |
|    (GPU Worker)       |                    |     (Orchestrator)      |
+-----------------------+                    +-------------------------+
            |                                             |
   [FFmpeg Exception!]                                    |
            |                                             |
            v                                             |
 1. Catch error in Python                                 |
 2. Is this the user's fault?                             |
    (e.g., Unreadable file)                               |
            |                                             |
            v                                             |
 3. Write to Mongo:                                       |
    status = "failed"                                     |
    failure_reason = "unreadable_source"                  |
    error = "FFmpeg: channel layout failed"               |
            |                                             |
       [Pod Dies]                                         |
                                                          |
                                                          v
                                              4. Read Mongo State
                                                          |
                                                          v
                                              5. Check `failure_reason`
                                                 Is it terminal?
                                                 (Yes, "unreadable_source")
                                                          |
                                                          v
                                              6. BREAK RETRY LOOP IMMEDIATELY!
                                                 Raise TerminalStageError
```

### The Information Black Hole

The second architectural fix in PR #9 was regarding telemetry. 

When a pod dies in Kubernetes/Runpod, its stdout/stderr logs often vanish with it. The Orchestrator only knew the pod died, so it threw a generic error: `RuntimeError: job marked failed in Mongo`.

As architects, we cannot debug a system that swallows errors. PR #9 forces the Orchestrator to read the specific `error` string out of Mongo and append it to the crash log. 

**Bad:** `RuntimeError: stage gpu: job marked failed in Mongo`
**Good:** `TerminalStageError: stage gpu failed terminally [unreadable_source]: FFmpeg get channel layout from speaker positions failed`

## Final Takeaways for the Team
1. **Decouple your dependencies:** If you don't need a shared library, use a static binary.
2. **Classify your errors:** A network timeout gets a retry. A corrupted file gets an immediate rejection.
3. **Never swallow the root cause:** If a distributed worker dies, it MUST leave a suicide note in a persistent datastore before the orchestrator cleans up the corpse.
