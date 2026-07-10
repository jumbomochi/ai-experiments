"""Pull submitted argilla records and write validated annotated.jsonl."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import argilla as rg
from pydantic import ValidationError

from shared.goldsets.schema import GoldExample, SeedExample


def _build_expected_from_answers(answers: dict) -> dict:
    """Build an expected dict from annotator answers. Raises ValueError for unknown types."""
    expected_type = answers.get("expected_type")
    if expected_type in {"exact", "set"}:
        raw_value = answers.get("expected_value", "")
        if expected_type == "set":
            value = [v.strip() for v in raw_value.split("|") if v.strip()]
        else:
            value = raw_value.strip()
        return {"type": expected_type, "value": value}
    elif expected_type == "rubric":
        rubric_text = (answers.get("expected_value") or "").strip()
        reference = (answers.get("reference_answer") or "").strip() or None
        return {"type": "rubric", "rubric": rubric_text, "reference": reference}
    raise ValueError(f"unknown expected_type={expected_type!r}")


def export_lane(
    lane: str,
    out_path: Path,
    argilla_url: str,
    api_key: str,
    seed_path: Path | None = None,
) -> int:
    """Export submitted records to annotated JSONL. Returns count exported.

    Exits non-zero (via sys.exit) if any record fails expected-structure validation.

    When seed_path is provided, inputs, prompt_template, source, and provenance_tag
    are re-joined from the seed file by example_id. never_to_third_party is always
    taken from the argilla annotation, not the seed.
    """
    seed_lookup: dict[str, SeedExample] = {}
    if seed_path is not None and seed_path.exists():
        with seed_path.open() as sf:
            for line in sf:
                line = line.strip()
                if not line:
                    continue
                s = SeedExample.model_validate(json.loads(line))
                seed_lookup[s.example_id] = s

    client = rg.Argilla(api_url=argilla_url, api_key=api_key)
    dataset = client.datasets(name=f"lane-{lane}")
    if dataset is None:
        print(f"[export] ERROR: dataset lane-{lane} not found in argilla", file=sys.stderr)
        sys.exit(1)

    exported: list[dict] = []
    validation_errors: list[str] = []

    for record in dataset.records(with_responses=True):
        # Find submitted response (annotator confirmed the annotation)
        submitted = None
        responses = record.responses or {}
        for resp in responses.values():
            if getattr(resp, "status", None) == "submitted":
                submitted = resp
                break
        if submitted is None:
            continue

        answers = {q: v.value for q, v in (submitted.answers or {}).items()}

        try:
            expected = _build_expected_from_answers(answers)
        except ValueError as e:
            validation_errors.append(f"record {record.id}: {e}")
            continue

        never_ttp = answers.get("never_to_third_party", "true")
        seed = seed_lookup.get(record.id)
        row = {
            "example_id": record.id,
            "lane": lane,
            "annotator": "argilla",
            "annotated_at": str(record.updated_at.date()) if record.updated_at else "2026-01-01",
            "prompt_template": seed.prompt_template if seed else "qa",
            "inputs": dict(seed.inputs) if seed else {},
            "expected": expected,
            "source": seed.source if seed else None,
            "provenance_tag": seed.provenance_tag if seed else "private",
            "never_to_third_party": never_ttp == "true",
            "tags": answers.get("tags") or [],
            "contamination_risk": answers.get("contamination_risk", "none"),
        }

        # Do NOT call GoldExample.model_validate(row) — inputs/prompt_template may be stubs
        # when no seed file is provided and would fail validation. Only the expected structure
        # has been validated above.
        exported.append(row)

    if validation_errors:
        for err in validation_errors:
            print(f"[export] VALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in exported:
            f.write(json.dumps(row) + "\n")

    return len(exported)
