"""Request shapes shared by the HTTP routes and the MCP tools.

One definition per call, used by both surfaces, so the two cannot drift.

They drifted before: `spacepilot_decompose_storyboard` documented
"Number of scenes (4-10)" and validated nothing, so an MCP caller asking for
50 got 10 back labelled `"status": "success"` while the same body over HTTP
was a 422. The MCP caller had no way to learn its request had been changed.

These models import pydantic only — never fastapi — so the stdio MCP server
can validate against them without pulling a web framework into its process.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


SCENE_COUNT_MIN, SCENE_COUNT_MAX = 4, 10
DURATION_MIN_SEC, DURATION_MAX_SEC = 10.0, 300.0


class StoryboardDecomposeRequest(BaseModel):
    script: str
    target_duration_sec: float = Field(default=60.0, ge=DURATION_MIN_SEC, le=DURATION_MAX_SEC)
    scene_count: int = Field(default=6, ge=SCENE_COUNT_MIN, le=SCENE_COUNT_MAX)
    style: str = "cinematic"
    model: str = "gemini-3.7-flash"
    character_seed: Optional[int] = None


class LocalNarrativeDecomposeRequest(BaseModel):
    script: str
    target_duration_sec: float = Field(default=60.0, ge=DURATION_MIN_SEC, le=DURATION_MAX_SEC)
    scene_count: int = Field(default=6, ge=SCENE_COUNT_MIN, le=SCENE_COUNT_MAX)
    style: str = "cinematic"
    character_seed: Optional[int] = None


class TrainLoRARequest(BaseModel):
    name: str
    base_model: str
    image_paths: List[str]
    trigger_word: str
    rank: int = 16
    alpha: float = 16.0
    target_modules: Optional[List[str]] = None
    steps: int = 500
    lr: float = 1e-4

    @field_validator("rank")
    @classmethod
    def validate_rank(cls, v):
        if v <= 0 or (v & (v - 1)) != 0:
            raise ValueError("rank must be > 0 and a power of 2")
        return v

    @field_validator("alpha")
    @classmethod
    def validate_alpha(cls, v):
        if v <= 0:
            raise ValueError("alpha must be > 0")
        return v


# The bounds a caller is told about when it breaks one. Pydantic names only
# the rule that fired ("less than or equal to 10"), which leaves the caller
# guessing at the other end of the range.
RANGES = {
    "scene_count": (SCENE_COUNT_MIN, SCENE_COUNT_MAX),
    "target_duration_sec": (DURATION_MIN_SEC, DURATION_MAX_SEC),
}


def describe(error: ValidationError) -> str:
    """Render a validation failure the way a caller can act on it.

    Names the field, the rule, the value it was given and the whole allowed
    range — an agent told only "invalid input" retries with the same number.
    """
    parts = []
    for item in error.errors():
        field = ".".join(str(piece) for piece in item["loc"]) or "request"
        detail = item["msg"].removeprefix("Value error, ")
        part = f"{field}: {detail} (got {item.get('input')!r})"
        if field in RANGES:
            low, high = RANGES[field]
            part += f"; allowed range is {low} to {high}"
        parts.append(part)
    return "; ".join(parts)
