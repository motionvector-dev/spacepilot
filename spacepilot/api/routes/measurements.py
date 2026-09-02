"""Read-only corpus endpoints for agents and local tools."""

from fastapi import APIRouter, HTTPException

from spacepilot.services.corpus import (
    CorpusReadError,
    measurement_payload,
    summary_payload,
    systems_payload,
)


router = APIRouter(prefix="/api", tags=["measurements"])


def _unavailable(exc: CorpusReadError) -> HTTPException:
    # Do not expose a traceback or turn a corrupt corpus into a plausible empty
    # successful response.  The message names the failed source truthfully.
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/measurements")
def get_measurements():
    """Every real observation, including stream-defining contention metadata."""
    try:
        return measurement_payload()
    except CorpusReadError as exc:
        raise _unavailable(exc) from exc


@router.get("/systems")
def get_systems():
    """Every probed system record visible to this installation."""
    try:
        return systems_payload()
    except CorpusReadError as exc:
        raise _unavailable(exc) from exc


@router.get("/summary")
def get_summary():
    """Measured performance summaries; solo and observed streams never merge."""
    try:
        return summary_payload()
    except CorpusReadError as exc:
        raise _unavailable(exc) from exc
