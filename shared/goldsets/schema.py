"""Per-example JSONL record schema (spec §3)."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_LANES = {"general", "sea", "japanese", "ocr", "finance"}
ALLOWED_EXPECTED_TYPES = {"exact", "set", "rubric"}
EXAMPLE_ID_RE = re.compile(r"^ex_[a-z]+_[a-z0-9]+$")


class Expected(BaseModel):
    type: Literal["exact", "set", "rubric"]
    value: Any


class GoldExample(BaseModel):
    example_id: str
    lane: str
    source: str | None = None
    annotator: str
    annotated_at: date
    prompt_template: str
    inputs: dict[str, Any]
    expected: Expected
    provenance_tag: Literal["private", "public", "public-derived"] = "private"
    never_to_third_party: bool = True
    tags: list[str] = Field(default_factory=list)
    contamination_risk: Literal["none", "low", "high", "known-in-corpus"] = "none"

    @field_validator("example_id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        if not EXAMPLE_ID_RE.match(v):
            raise ValueError(f"example_id {v!r} must match {EXAMPLE_ID_RE.pattern}")
        return v

    @field_validator("lane")
    @classmethod
    def _lane_known(cls, v: str) -> str:
        if v not in ALLOWED_LANES:
            raise ValueError(f"lane {v!r} not in {sorted(ALLOWED_LANES)}")
        return v
