"""Runtime routes — what can execute a model, and installing it.

The install is a background job with progress, like a model download, because
resolving and installing takes long enough that a request would time out and
short enough that a person will sit and watch it.

Nothing here installs without having first resolved what would change. The
preview is a separate call on purpose, so a caller has to look before it acts.
"""

import asyncio
import time
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from spacepilot.api.deps import require_token

router = APIRouter(prefix="/api/runtimes", tags=["runtimes"])


class InstallJob(BaseModel):
    job_id: str
    runtime_id: str
    status: str            # pending | resolving | installing | completed | failed | refused
    message: Optional[str] = None
    version: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    changed: Optional[dict] = None


_jobs: Dict[str, InstallJob] = {}


@router.get("")
def list_runtimes():
    """Every runtime, with whether it is installed in this interpreter."""
    from spacepilot.device_probe import probe_local_device
    from spacepilot import runtimes as rt

    profile = probe_local_device()
    out = []
    for r in rt.runtimes().values():
        st = rt.check(r)
        out.append({
            **{k: v for k, v in r.to_dict().items()},
            "status": st.to_dict(),
            # Usable here means the silicon matches and the interpreter is
            # compatible — separate from whether it happens to be installed.
            "usable_here": bool(profile.backend and profile.backend in r.backends)
                           and st.python_compatible,
            # Per runtime, because an `isolated` one does not live in the
            # interpreter named below. Free: `check()` already resolved it.
            "interpreter": st.interpreter or rt.interpreter(),
            "isolated": r.install.isolated,
        })
    return {
        "backend": profile.backend,
        "chip": profile.chip,
        # The shared interpreter. An isolated runtime reports its own above.
        "interpreter": rt.interpreter(),
        "runtimes": out,
    }


@router.get("/{runtime_id}/preview", dependencies=[Depends(require_token)])
async def preview_install(runtime_id: str):
    """Resolve what installing would change, without changing anything.

    Runs pip's resolver, which reaches the network, so it is off the event loop.
    """
    from spacepilot import runtimes as rt

    r = rt.runtimes().get(runtime_id)
    if not r:
        raise HTTPException(404, f"No runtime '{runtime_id}'")

    imp = await asyncio.to_thread(rt.preview, r)
    return {
        "runtime_id": runtime_id,
        "command": " ".join(rt.install_command(r, probe=True)),
        # The interpreter this runtime installs into, which for an
        # `isolated` runtime is its own venv rather than the daemon's.
        "interpreter": rt.runtime_python(runtime_id),
        "isolated": r.install.isolated,
        **imp.to_dict(),
    }


class InstallRequest(BaseModel):
    allow_downgrade: bool = False


@router.post("/{runtime_id}/install", dependencies=[Depends(require_token)])
async def start_install(runtime_id: str, req: InstallRequest = InstallRequest()):
    """Start an install. Refuses a resolution that would downgrade anything."""
    from spacepilot import runtimes as rt

    r = rt.runtimes().get(runtime_id)
    if not r:
        raise HTTPException(404, f"No runtime '{runtime_id}'")

    st = rt.check(r)
    if not st.python_compatible:
        raise HTTPException(409, st.python_note or "incompatible interpreter")

    job_id = uuid.uuid4().hex[:12]
    job = InstallJob(job_id=job_id, runtime_id=runtime_id, status="pending",
                     started_at=time.time())
    _jobs[job_id] = job
    asyncio.create_task(_run(job, r, req.allow_downgrade))
    return job.model_dump()


async def _run(job: InstallJob, r, allow_downgrade: bool) -> None:
    from spacepilot import runtimes as rt

    try:
        job.status = "resolving"
        job.message = f"resolving {r.install.package}"
        imp = await asyncio.to_thread(rt.preview, r)
        job.changed = imp.to_dict()

        if imp.error:
            job.status, job.error = "failed", imp.error
            return

        if imp.is_disruptive and not allow_downgrade:
            # Stop here rather than proceed. A downgrade in a shared
            # environment breaks something else, later, with no clue why.
            job.status = "refused"
            job.error = ("would downgrade "
                         + ", ".join(f"{n} {a} to {b}" for n, a, b in imp.downgrades))
            job.finished_at = time.time()
            return

        job.status = "installing"
        job.message = f"installing {r.install.package}"
        st = await asyncio.to_thread(rt.install, r)
        job.version = st.version
        if st.installed and not st.below_minimum:
            job.status, job.message = "completed", f"{r.name} {st.version} imports cleanly"
        else:
            job.status, job.error = "failed", st.reason
    except Exception as e:
        job.status, job.error = "failed", str(e)
    finally:
        job.finished_at = time.time()


@router.get("/jobs/{job_id}", dependencies=[Depends(require_token)])
def install_progress(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"No install job '{job_id}'")
    return job.model_dump()
