"""JSONL → Postgres loader for gold sets.

Idempotent on `(version, git_commit_sha)`: a second call with identical args
is a no-op. A second call with the same `version` but a different sha is an
immutability violation and raises.

The loader inserts examples then sets gold_set_version.released = true, which
arms the immutability trigger on gold_example.
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from shared.db.connection import connect
from shared.goldsets.schema import GoldExample


def _example_uuid(example_id: str) -> uuid.UUID:
    """Map our ex_<lane>_<suffix> id to a deterministic uuid5 for the uuid PK."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"goldsets://{example_id}")


def load_jsonl_to_postgres(
    jsonl_path: Path,
    version: str,
    git_commit_sha: str,
    test: bool = False,
) -> int:
    """Returns the number of examples loaded; 0 only on an idempotent no-op
    (same (version, sha) already loaded). Empty JSONL is a hard error — see
    the guard below.
    """
    examples: list[GoldExample] = []
    with jsonl_path.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{jsonl_path}:{line_no}: invalid JSON: {e}") from e
            try:
                examples.append(GoldExample.model_validate(raw))
            except ValidationError as e:
                raise ValueError(
                    f"{jsonl_path}:{line_no}: schema validation failed: {e}"
                ) from e

    if not examples:
        raise ValueError(
            f"{jsonl_path}: JSONL contains no valid examples; "
            f"refusing to load an empty gold set"
        )

    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT git_commit_sha, released FROM gold_set_version WHERE version=%s",
            (version,),
        )
        row = cur.fetchone()
        if row is not None:
            existing_sha, existing_released = row
            if existing_sha != git_commit_sha:
                raise ValueError(
                    f"immutability violation: version={version} already loaded "
                    f"at sha={existing_sha!r}; refusing to overwrite with {git_commit_sha!r}"
                )
            # Same (version, sha) → idempotent no-op
            return 0

        lane_counts = Counter(e.lane for e in examples)
        cur.execute(
            "INSERT INTO gold_set_version (version, git_commit_sha, lane_counts, released) "
            "VALUES (%s, %s, %s::jsonb, false)",
            (version, git_commit_sha, json.dumps(dict(lane_counts))),
        )
        for ex in examples:
            cur.execute(
                """
                INSERT INTO gold_example (
                    version, example_id, lane, source, annotator, annotated_at,
                    prompt_template, inputs, expected, provenance_tag,
                    never_to_third_party, tags, contamination_risk
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s::jsonb, %s::jsonb, %s,
                    %s, %s, %s
                )
                """,
                (
                    version, _example_uuid(ex.example_id), ex.lane,
                    ex.source, ex.annotator, ex.annotated_at,
                    ex.prompt_template,
                    json.dumps(ex.inputs),
                    json.dumps(ex.expected.model_dump()),
                    ex.provenance_tag,
                    ex.never_to_third_party,
                    ex.tags, ex.contamination_risk,
                ),
            )
        # Arm immutability AFTER inserts succeed
        cur.execute(
            "UPDATE gold_set_version SET released = true WHERE version = %s",
            (version,),
        )

    return len(examples)
