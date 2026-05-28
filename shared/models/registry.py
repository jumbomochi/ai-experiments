"""Postgres-backed model registry: load YAMLs and sync into model_manifest."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from shared.db.connection import connect
from shared.models.manifest import ModelManifest, load_manifest_yaml

REGISTRY_DIR = Path(__file__).resolve().parent / "registry"


def discover_yamls(directory: Path = REGISTRY_DIR) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.glob("*.yaml") if p.is_file())


def sync_to_postgres(manifests: Iterable[ModelManifest], test: bool = False) -> None:
    """UPSERT each manifest into model_manifest."""
    with connect(test=test) as conn, conn.cursor() as cur:
        for m in manifests:
            raw = m.model_dump()
            cur.execute(
                """
                INSERT INTO model_manifest (
                    id, family, size, revision, quantization,
                    runtime, runtime_version, target_host, endpoint,
                    capabilities, context_window, default_sampling, raw
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    family = EXCLUDED.family,
                    size = EXCLUDED.size,
                    revision = EXCLUDED.revision,
                    quantization = EXCLUDED.quantization,
                    runtime = EXCLUDED.runtime,
                    runtime_version = EXCLUDED.runtime_version,
                    target_host = EXCLUDED.target_host,
                    endpoint = EXCLUDED.endpoint,
                    capabilities = EXCLUDED.capabilities,
                    context_window = EXCLUDED.context_window,
                    default_sampling = EXCLUDED.default_sampling,
                    raw = EXCLUDED.raw,
                    loaded_at = now()
                """,
                (
                    m.id, m.family, m.size, m.revision, m.quantization,
                    m.runtime, m.runtime_version, m.target_host, m.endpoint,
                    m.capabilities, m.context_window,
                    json.dumps(raw["default_sampling"]),
                    json.dumps(raw),
                ),
            )


def sync_all(test: bool = False) -> int:
    """Load every YAML under REGISTRY_DIR and sync. Returns count.

    Raises ValueError if two YAML files declare the same model id.
    """
    paths = discover_yamls(REGISTRY_DIR)
    manifests = [load_manifest_yaml(p) for p in paths]
    counts = Counter(m.id for m in manifests)
    dupes = sorted(mid for mid, n in counts.items() if n > 1)
    if dupes:
        raise ValueError(f"duplicate model ids across YAML files: {dupes}")
    sync_to_postgres(manifests, test=test)
    return len(manifests)


def resolve(model_id: str, test: bool = False) -> ModelManifest:
    """Look up a manifest by id from Postgres."""
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute("SELECT raw FROM model_manifest WHERE id = %s", (model_id,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"no model_manifest with id={model_id!r}")
    raw = row[0]  # psycopg returns jsonb as already-decoded dict
    return ModelManifest.model_validate(raw)
