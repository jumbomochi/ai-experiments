"""Judge plumbing: deterministic scorer + aggregation across judges."""

import json
from pathlib import Path

import yaml

from shared.db.connection import connect
from shared.eval.judges.deterministic import score as deterministic_score, DeterministicConfig
from shared.eval.judges.aggregate import aggregate, Judgement

CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


def register_bundle(version: str, test: bool = False) -> None:
    path = CONFIGS_DIR / f"{version}.yaml"
    bundle = yaml.safe_load(path.read_text())
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO judge_config (version, bundle) VALUES (%s, %s::jsonb) "
            "ON CONFLICT (version) DO UPDATE SET bundle = EXCLUDED.bundle",
            (version, json.dumps(bundle)),
        )


__all__ = [
    "deterministic_score",
    "DeterministicConfig",
    "aggregate",
    "Judgement",
    "register_bundle",
]
