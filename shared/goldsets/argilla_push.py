"""Push seed JSONL to argilla as unannotated records; idempotent on example_id."""
from __future__ import annotations

import json
from pathlib import Path

import argilla as rg

from shared.goldsets.render import render_prompt
from shared.goldsets.schema import SeedExample

_TEMPLATE_ROOT = Path(__file__).resolve().parent.parent.parent / "templates"


def _build_settings() -> rg.Settings:
    """Build argilla dataset settings lazily (avoids module-level network calls)."""
    fields = [
        rg.TextField(name="rendered_prompt"),
        rg.TextField(name="source"),
    ]
    questions = [
        rg.LabelQuestion(name="expected_type", labels=["exact", "set", "rubric"]),
        rg.TextQuestion(name="expected_value", required=False,
                        description="For exact/set: the answer. For rubric: the scoring rubric text."),
        rg.TextQuestion(name="reference_answer", required=False,
                        description="Optional reference answer for rubric type."),
        rg.LabelQuestion(name="never_to_third_party", labels=["true", "false"]),
        rg.MultiLabelQuestion(name="tags",
                              labels=["smoke", "hard", "multilingual", "finance", "ocr", "private"]),
        rg.LabelQuestion(name="contamination_risk",
                         labels=["none", "low", "high", "known-in-corpus"]),
    ]
    return rg.Settings(
        fields=fields,
        questions=questions,
        metadata=[rg.TermsMetadataProperty(name="example_id")],
    )


def push_lane(
    seed_path: Path,
    lane: str,
    argilla_url: str,
    api_key: str,
    template_root: Path | None = None,
) -> int:
    """Push unannotated seed records to argilla. Returns count of new records pushed."""
    template_root = template_root or _TEMPLATE_ROOT
    client = rg.Argilla(api_url=argilla_url, api_key=api_key)
    dataset_name = f"lane-{lane}"

    # Get or create dataset
    dataset = client.datasets(name=dataset_name)
    if dataset is None:
        dataset = rg.Dataset(name=dataset_name, settings=_build_settings(), client=client)
        dataset.create()

    # Collect existing IDs to skip (idempotency)
    existing_ids = {r.id for r in dataset.records(fields=[])}

    # Load seed
    seeds: list[SeedExample] = []
    with seed_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            seeds.append(SeedExample.model_validate(json.loads(line)))

    new_records = []
    for seed in seeds:
        if seed.example_id in existing_ids:
            continue
        try:
            rendered = render_prompt(template_root, seed.prompt_template, seed.inputs)
        except Exception:
            rendered = str(seed.inputs)  # fallback if template not found
        new_records.append(rg.Record(
            id=seed.example_id,
            fields={
                "rendered_prompt": rendered,
                "source": seed.source or "",
            },
            metadata={"example_id": seed.example_id},
        ))

    if new_records:
        dataset.records.add(new_records)

    return len(new_records)
