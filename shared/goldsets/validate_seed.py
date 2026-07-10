"""Validate a seed JSONL against SeedExample schema before pushing to argilla."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from shared.goldsets.schema import SeedExample


def validate_seed(path: Path) -> list[str]:
    """Return a list of error strings; empty list means the file is valid."""
    errors: list[str] = []
    line_count = 0

    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"line {line_no}: invalid JSON: {e}")
                continue
            try:
                SeedExample.model_validate(raw)
            except ValidationError as e:
                for err in e.errors():
                    field = ".".join(str(loc) for loc in err["loc"])
                    errors.append(f"line {line_no}: {field}: {err['msg']}")

    if line_count == 0:
        errors.append("empty seed file — no examples found")

    return errors
