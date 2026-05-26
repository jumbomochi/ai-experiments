# Eval Substrate — Sprint 1 (Mac-mini End-to-End) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Mac-mini-only sovereign eval loop that hits a small local model (Ollama, OpenAI-compatible) behind the inference contract, stores reproducible records in Postgres, and scores a 3-example public seed via the deterministic judge — proving all four hard-to-reverse decisions wire together end-to-end.

**Architecture:** Single-process Python orchestration (`shared/eval/runner/`) calls a local Ollama endpoint (`shared/inference/`) using manifests loaded from YAML (`shared/models/`), scores against examples loaded from JSONL (`shared/goldsets/`), via a deterministic judge (`shared/eval/judges/`), with costs computed from a YAML rate-card (`shared/eval/cost/`). All state persists to Postgres 16 via plain `psycopg`. The end-to-end smoke is the `0001-inference-contract-validation` experiment.

**Tech Stack:** Python 3.12, uv, Postgres 16 + pgvector (extension installed but unused in Sprint 1), Ollama for local serving, `psycopg[binary]>=3.2`, `pydantic>=2.8`, `PyYAML>=6.0`, `Jinja2>=3.1`, `requests>=2.32` (already a dep), pytest.

**Out of scope for this plan (deferred to follow-up plans):**
- DGX Spark + cloud-burst targets (arrives S2)
- Specialist + generalist LLM judges (S3)
- Human calibration set + κ measurement (S3)
- Bias stress tests (S3)
- The private `ai-experiments-goldsets` git repo (created in S1 wk2, but its full curation workflow lands in S2)
- Lane-depth gold sets beyond the 3-example seed (S4)
- Migration *evolution* (this plan ships `001_init.sql` only)

**Spec reference:** `docs/superpowers/specs/2026-05-14-evaluation-system-design.md` (commit `4b54831`).

---

## File structure

Files this plan creates or modifies:

```
ai-experiments/
├── pyproject.toml                                   # MODIFY: add baseline deps
├── EXPERIMENTS.md                                   # MODIFY: add row for 0001
├── ROADMAP.md                                       # MODIFY: Phase 1 status → in progress
├── migrations/
│   ├── 001_init.sql                                 # CREATE: the 7 tables
│   └── README.md                                    # CREATE: how migrations work
├── shared/
│   ├── db/
│   │   ├── __init__.py                              # CREATE
│   │   ├── connection.py                            # CREATE: psycopg connection helper
│   │   └── migrations.py                            # CREATE: applier (CLI: `python -m shared.db.migrations apply`)
│   ├── inference/
│   │   ├── __init__.py                              # CREATE
│   │   ├── client.py                                # CREATE: InferenceClient
│   │   ├── errors.py                                # CREATE: error classification
│   │   └── retry.py                                 # CREATE: backoff loop
│   ├── models/
│   │   ├── __init__.py                              # CREATE
│   │   ├── manifest.py                              # CREATE: ModelManifest pydantic model
│   │   ├── registry.py                              # CREATE: load YAMLs, sync to Postgres
│   │   └── registry/
│   │       └── qwen2.5-0.5b-instruct-ollama.yaml    # CREATE: first manifest
│   ├── goldsets/
│   │   ├── __init__.py                              # CREATE
│   │   ├── schema.py                                # CREATE: pydantic models for JSONL records
│   │   ├── loader.py                                # CREATE: validator + idempotent loader
│   │   └── render.py                                # CREATE: Jinja2 prompt rendering
│   └── eval/
│       ├── __init__.py                              # CREATE
│       ├── cost/
│       │   ├── __init__.py                          # CREATE
│       │   ├── accountant.py                        # CREATE: rate-card math
│       │   └── rate_cards/
│       │       └── mac-mini.yaml                    # CREATE: $/Mtok for the Mac target
│       ├── judges/
│       │   ├── __init__.py                          # CREATE
│       │   ├── deterministic.py                     # CREATE: deterministic scorer
│       │   ├── aggregate.py                         # CREATE: aggregation rule
│       │   └── configs/
│       │       └── v0.1.yaml                        # CREATE: deterministic-only bundle
│       └── runner/
│           ├── __init__.py                          # CREATE
│           ├── preflight.py                         # CREATE: 6-step preflight
│           ├── runner.py                            # CREATE: campaign orchestration
│           ├── teardown.py                          # CREATE: hook interface + LocalTeardownHook
│           └── cli.py                               # CREATE: `python -m shared.eval.runner ...`
├── experiments/
│   └── 0001-inference-contract-validation/
│       ├── README.md                                # CREATE: Hypothesis/Setup/Method/Results/Conclusion
│       ├── seed.jsonl                               # CREATE: 3 public examples
│       ├── prompt_templates/
│       │   └── general/multi-choice.j2              # CREATE: tiny Jinja template
│       └── run.sh                                   # CREATE: convenience launcher
└── tests/
    ├── __init__.py                                  # CREATE
    ├── conftest.py                                  # CREATE: postgres test fixture, mock OpenAI server
    ├── shared/
    │   ├── __init__.py                              # CREATE
    │   ├── db/test_migrations.py                    # CREATE
    │   ├── inference/test_client.py                 # CREATE
    │   ├── inference/test_errors.py                 # CREATE
    │   ├── models/test_manifest.py                  # CREATE
    │   ├── models/test_registry.py                  # CREATE
    │   ├── goldsets/test_schema.py                  # CREATE
    │   ├── goldsets/test_loader.py                  # CREATE
    │   ├── goldsets/test_render.py                  # CREATE
    │   ├── eval/test_cost.py                        # CREATE
    │   ├── eval/test_deterministic.py               # CREATE
    │   ├── eval/test_aggregate.py                   # CREATE
    │   ├── eval/test_preflight.py                   # CREATE
    │   └── eval/test_runner.py                      # CREATE
    └── integration/
        └── test_end_to_end.py                       # CREATE: full campaign via mock endpoint
```

---

## Task 0: Add baseline runtime deps to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the four new root deps and `psycopg` to dev for tests**

Edit `pyproject.toml` so the `[project]` block reads:

```toml
[project]
name = "ai-experiments"
version = "0.1.0"
description = "AI and local-LLM experiments — planning, code, and results."
requires-python = ">=3.10"
dependencies = [
    "huggingface-hub>=0.25",
    "datasets>=2.20",
    "numpy>=1.26",
    "pandas>=2.2",
    "matplotlib>=3.8",
    "rich>=13.7",
    "python-dotenv>=1.0",
    "requests>=2.32",
    "psycopg[binary]>=3.2",
    "pydantic>=2.8",
    "PyYAML>=6.0",
    "Jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.6",
    "pytest>=8.0",
    "ipykernel>=6.29",
    "jupyterlab>=4.2",
]
```

- [ ] **Step 2: Sync the env**

Run: `uv sync --extra dev`
Expected: completes without error; `uv.lock` updates.

- [ ] **Step 3: Smoke-import**

Run: `uv run python -c "import psycopg, pydantic, yaml, jinja2; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add baseline deps for eval substrate (psycopg, pydantic, pyyaml, jinja2)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1: Postgres + pgvector on the Mac mini

This task is operator-mediated (system install). The plan documents the exact commands; the engineer runs them.

**Files:**
- Create: `docs/notes/postgres-setup.md`

- [ ] **Step 1: Install Postgres 16 via Homebrew**

Run: `brew install postgresql@16`
Expected: installs without error; reports the data directory under `/opt/homebrew/var/postgresql@16`.

- [ ] **Step 2: Start the Postgres service**

Run: `brew services start postgresql@16`
Expected: `Successfully started 'postgresql@16'`

- [ ] **Step 3: Verify Postgres is up**

Run: `/opt/homebrew/opt/postgresql@16/bin/psql -d postgres -c 'SELECT version();'`
Expected: prints `PostgreSQL 16.x ...`.

- [ ] **Step 4: Create the `ai_experiments` and `ai_experiments_test` databases**

Run:
```bash
/opt/homebrew/opt/postgresql@16/bin/createdb ai_experiments
/opt/homebrew/opt/postgresql@16/bin/createdb ai_experiments_test
```
Expected: both complete silently.

- [ ] **Step 5: Install pgvector extension**

Run: `brew install pgvector`
Then in each DB:
```bash
/opt/homebrew/opt/postgresql@16/bin/psql -d ai_experiments -c 'CREATE EXTENSION IF NOT EXISTS vector;'
/opt/homebrew/opt/postgresql@16/bin/psql -d ai_experiments_test -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```
Expected: `CREATE EXTENSION` printed for each.

- [ ] **Step 6: Add `DATABASE_URL` to `.env` (gitignored)**

Create `.env` with:
```
DATABASE_URL=postgresql://$(whoami)@localhost:5432/ai_experiments
DATABASE_URL_TEST=postgresql://$(whoami)@localhost:5432/ai_experiments_test
```
Confirm `.env` is in `.gitignore` (it should be from the repo-design spec — verify by `git check-ignore .env` → exits 0 and prints `.env`).

- [ ] **Step 7: Document the setup**

Create `docs/notes/postgres-setup.md`:

```markdown
# Postgres setup on the Mac mini

Single-user, single-machine, no remote access. Sufficient for the eval substrate
through Phase 6.

## Install

    brew install postgresql@16 pgvector
    brew services start postgresql@16

## Databases

    createdb ai_experiments      # production
    createdb ai_experiments_test # pytest fixtures

Both have the `vector` extension enabled:

    psql -d ai_experiments      -c 'CREATE EXTENSION IF NOT EXISTS vector;'
    psql -d ai_experiments_test -c 'CREATE EXTENSION IF NOT EXISTS vector;'

## Connection strings

Stored in `.env` (gitignored):

    DATABASE_URL=postgresql://<user>@localhost:5432/ai_experiments
    DATABASE_URL_TEST=postgresql://<user>@localhost:5432/ai_experiments_test

## Notes

- pgvector is installed but *unused* through Sprint 1. The memory adapter (Phase 5)
  is the first consumer.
- No replication, no backups, no remote auth in v0.1. The Mac mini's filesystem
  Time Machine backup is the disaster recovery story.
```

- [ ] **Step 8: Commit**

```bash
git add docs/notes/postgres-setup.md
git commit -m "Add Postgres setup notes for Mac mini

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Migration applier + `001_init.sql`

**Files:**
- Create: `shared/db/__init__.py`
- Create: `shared/db/connection.py`
- Create: `shared/db/migrations.py`
- Create: `migrations/001_init.sql`
- Create: `migrations/README.md`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/shared/__init__.py`
- Create: `tests/shared/db/test_migrations.py`

- [ ] **Step 1: Create the empty test packages**

```bash
mkdir -p tests/shared/db tests/integration
touch tests/__init__.py tests/shared/__init__.py
```

- [ ] **Step 2: Create the connection helper**

`shared/db/__init__.py`:

```python
"""Postgres helpers — connection and migrations."""
```

`shared/db/connection.py`:

```python
"""Single source of truth for opening Postgres connections.

Reads `DATABASE_URL` from environment (loaded from `.env` via python-dotenv).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from dotenv import load_dotenv

load_dotenv()


def database_url(test: bool = False) -> str:
    var = "DATABASE_URL_TEST" if test else "DATABASE_URL"
    url = os.environ.get(var)
    if not url:
        raise RuntimeError(f"{var} is not set; see docs/notes/postgres-setup.md")
    return url


@contextmanager
def connect(test: bool = False) -> Iterator[psycopg.Connection]:
    """Open a psycopg connection; commit on success, rollback on exception."""
    with psycopg.connect(database_url(test=test)) as conn:
        yield conn
```

- [ ] **Step 3: Write the failing migration-applier test**

`tests/shared/db/__init__.py`:

```python
```

`tests/shared/db/test_migrations.py`:

```python
"""Tests for the migration applier."""
from __future__ import annotations

import psycopg

from shared.db.connection import connect
from shared.db.migrations import apply_all, applied_migrations


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def test_apply_all_creates_schema_migrations_and_seven_tables() -> None:
    _reset_test_db()
    apply_all(test=True)
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname='public' ORDER BY tablename"
        )
        tables = {row[0] for row in cur.fetchall()}
    expected = {
        "schema_migrations",
        "model_manifest",
        "gold_set_version",
        "gold_example",
        "judge_config",
        "run",
        "result",
        "judgement",
    }
    assert tables == expected, f"unexpected tables: {tables ^ expected}"


def test_apply_all_is_idempotent() -> None:
    _reset_test_db()
    apply_all(test=True)
    first = applied_migrations(test=True)
    apply_all(test=True)  # second apply
    second = applied_migrations(test=True)
    assert first == second
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `uv run pytest tests/shared/db/test_migrations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shared.db.migrations'`.

- [ ] **Step 5: Write `migrations/001_init.sql`**

`migrations/001_init.sql`:

```sql
-- 001_init.sql
-- Initial schema for the eval substrate.
-- See docs/superpowers/specs/2026-05-14-evaluation-system-design.md §2 (run-storage).

BEGIN;

-- Reference: registry of all model manifests (loaded from shared/models/registry/*.yaml).
CREATE TABLE model_manifest (
    id              text PRIMARY KEY,
    family          text NOT NULL,
    size            text NOT NULL,
    revision        text NOT NULL,
    quantization    text,
    runtime         text NOT NULL,
    runtime_version text NOT NULL,
    target_host     text NOT NULL,
    endpoint        text NOT NULL,
    capabilities    text[] NOT NULL DEFAULT '{}',
    context_window  int  NOT NULL,
    default_sampling jsonb NOT NULL,
    raw             jsonb NOT NULL,
    loaded_at       timestamptz NOT NULL DEFAULT now()
);

-- Reference: released gold-set snapshots.
CREATE TABLE gold_set_version (
    version        text PRIMARY KEY,
    released_at    timestamptz NOT NULL DEFAULT now(),
    git_commit_sha text,
    lane_counts    jsonb NOT NULL DEFAULT '{}'::jsonb,
    released       bool NOT NULL DEFAULT false,
    notes          text
);

-- Reference: examples in each released snapshot.
CREATE TABLE gold_example (
    version              text NOT NULL REFERENCES gold_set_version(version),
    example_id           uuid NOT NULL,
    lane                 text NOT NULL,
    source               text,
    annotator            text,
    annotated_at         date,
    prompt_template      text NOT NULL,
    inputs               jsonb NOT NULL,
    expected             jsonb NOT NULL,
    provenance_tag       text NOT NULL DEFAULT 'private',
    never_to_third_party bool NOT NULL DEFAULT true,
    tags                 text[] NOT NULL DEFAULT '{}',
    contamination_risk   text NOT NULL DEFAULT 'none',
    PRIMARY KEY (version, example_id)
);
CREATE INDEX gold_example_lane_version_idx ON gold_example (lane, version);

-- Trigger: once gold_set_version.released is true, no more inserts into gold_example for that version.
CREATE OR REPLACE FUNCTION gold_example_immutability() RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM gold_set_version
        WHERE version = NEW.version AND released = true
    ) THEN
        RAISE EXCEPTION 'gold_set_version % is released; no new inserts allowed', NEW.version;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER gold_example_immutability_trigger
    BEFORE INSERT OR UPDATE ON gold_example
    FOR EACH ROW EXECUTE FUNCTION gold_example_immutability();

-- Reference: versioned judge bundles.
CREATE TABLE judge_config (
    version     text PRIMARY KEY,
    released_at timestamptz NOT NULL DEFAULT now(),
    bundle      jsonb NOT NULL,
    notes       text
);

-- Spine: one campaign per row.
CREATE TABLE run (
    id                   uuid PRIMARY KEY,
    started_at           timestamptz NOT NULL DEFAULT now(),
    finished_at          timestamptz,
    status               text NOT NULL,
    model_id             text NOT NULL,
    model_manifest       jsonb NOT NULL,
    gold_set_version     text NOT NULL REFERENCES gold_set_version(version),
    judge_config_version text NOT NULL REFERENCES judge_config(version),
    judge_config         jsonb NOT NULL,
    max_cost_usd         numeric(10,4) NOT NULL,
    cost_actual_usd      numeric(10,4),
    wall_seconds         int,
    n_examples_total     int NOT NULL,
    n_examples_scored    int NOT NULL DEFAULT 0,
    n_examples_errored   int NOT NULL DEFAULT 0,
    summary_scores       jsonb,
    experiment_id        text,
    notes                text,
    error                jsonb
);
CREATE INDEX run_status_started_at_idx ON run (status, started_at);
CREATE INDEX run_model_id_started_at_idx ON run (model_id, started_at);
CREATE INDEX run_gold_set_version_idx ON run (gold_set_version);

-- Spine: one row per example per run.
CREATE TABLE result (
    id                       uuid PRIMARY KEY,
    run_id                   uuid NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    example_id               uuid NOT NULL,
    gold_set_version         text NOT NULL,
    rendered_prompt          text NOT NULL,
    response                 text,
    response_logprobs        jsonb,
    usage                    jsonb,
    cost_increment_usd       numeric(10,6) NOT NULL DEFAULT 0,
    wall_ms                  int,
    score                    numeric(6,4),
    score_kind               text,
    error_class              text,
    error_body               jsonb,
    nondeterministic_runtime bool NOT NULL DEFAULT false,
    started_at               timestamptz NOT NULL,
    finished_at              timestamptz
);
CREATE INDEX result_run_id_idx ON result (run_id);
CREATE INDEX result_run_id_example_id_idx ON result (run_id, example_id);
CREATE INDEX result_run_id_error_idx ON result (run_id) WHERE error_class IS NOT NULL;

-- Spine: one row per (result, judge).
CREATE TABLE judgement (
    id                 uuid PRIMARY KEY,
    result_id          uuid NOT NULL REFERENCES result(id) ON DELETE CASCADE,
    judge_role         text NOT NULL,
    judge_manifest     jsonb NOT NULL,
    rubric_id          text,
    rendered_prompt    text,
    raw_response       text,
    score              numeric(6,4),
    score_kind         text NOT NULL,
    rationale          text,
    parse_error        bool NOT NULL DEFAULT false,
    usage              jsonb,
    cost_increment_usd numeric(10,6) NOT NULL DEFAULT 0,
    wall_ms            int,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX judgement_result_id_idx ON judgement (result_id);
CREATE INDEX judgement_result_id_role_idx ON judgement (result_id, judge_role);

COMMIT;
```

- [ ] **Step 6: Write the migration applier**

`shared/db/migrations.py`:

```python
"""Minimal SQL migration applier.

Migrations are plain SQL files under `migrations/`, named `NNN_<slug>.sql` and
applied in lexical order. Applied IDs are recorded in `schema_migrations`.

CLI:  uv run python -m shared.db.migrations apply [--test]
      uv run python -m shared.db.migrations list  [--test]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from shared.db.connection import connect

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_RE = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def _ensure_schema_migrations(test: bool = False) -> None:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "id text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )


def applied_migrations(test: bool = False) -> set[str]:
    _ensure_schema_migrations(test=test)
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _discover() -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for p in sorted(MIGRATIONS_DIR.iterdir()):
        m = MIGRATION_RE.match(p.name)
        if m:
            entries.append((m.group(1), p))
    return entries


def apply_all(test: bool = False) -> list[str]:
    """Apply every migration not yet recorded; return the list applied this run."""
    _ensure_schema_migrations(test=test)
    applied = applied_migrations(test=test)
    new_ids: list[str] = []
    for mid, path in _discover():
        if mid in applied:
            continue
        sql = path.read_text()
        with connect(test=test) as conn, conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (id) VALUES (%s)", (mid,)
            )
        new_ids.append(mid)
    return new_ids


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["apply", "list"])
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    if args.cmd == "list":
        applied = applied_migrations(test=args.test)
        for mid, path in _discover():
            mark = "✓" if mid in applied else " "
            print(f"  {mark}  {mid}  {path.name}")
    else:
        new = apply_all(test=args.test)
        if new:
            print("applied:", ", ".join(new))
        else:
            print("nothing to apply")


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run pytest tests/shared/db/test_migrations.py -v`
Expected: 2 passed.

- [ ] **Step 8: Apply the migration against the production database**

Run: `uv run python -m shared.db.migrations apply`
Expected: `applied: 001`

- [ ] **Step 9: Document migrations**

`migrations/README.md`:

```markdown
# Migrations

Plain SQL files, sequentially numbered (`001_init.sql`, `002_*.sql`, ...).

## Apply

    uv run python -m shared.db.migrations apply         # production
    uv run python -m shared.db.migrations apply --test  # test database

Applied IDs are recorded in the `schema_migrations` table; re-applying is a no-op.

## Why this and not Alembic / sqitch

YAGNI for a single-developer, single-machine setup. Revisit when the project
needs multi-developer migrations, rollback support, or branch-aware ordering.

## Add a migration

1. Create `migrations/NNN_<slug>.sql` (NNN = next zero-padded integer).
2. Record the rationale in `docs/notes/instrumentation.md` per the ROADMAP
   instrumentation track.
3. Apply: `uv run python -m shared.db.migrations apply`.
```

- [ ] **Step 10: Commit**

```bash
git add migrations/ shared/db/ tests/shared/db/test_migrations.py tests/__init__.py tests/shared/__init__.py
git commit -m "Add Postgres schema + migration applier (001_init.sql, 7 tables)

Schema implements §2 of the eval-system spec: model_manifest, gold_set_version,
gold_example (with immutability trigger), judge_config, run, result, judgement.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `shared/inference/` — InferenceClient with error classification

**Files:**
- Create: `shared/inference/__init__.py`
- Create: `shared/inference/errors.py`
- Create: `shared/inference/retry.py`
- Create: `shared/inference/client.py`
- Create: `tests/shared/inference/__init__.py`
- Create: `tests/shared/inference/test_errors.py`
- Create: `tests/shared/inference/test_client.py`

- [ ] **Step 1: Write the failing test for error classification**

`tests/shared/inference/__init__.py`:

```python
```

`tests/shared/inference/test_errors.py`:

```python
"""Error-classification tests for the inference client."""
from __future__ import annotations

import pytest

from shared.inference.errors import classify, ErrorClass


@pytest.mark.parametrize(
    "status, expected",
    [
        (500, ErrorClass.RETRYABLE),
        (502, ErrorClass.RETRYABLE),
        (503, ErrorClass.RETRYABLE),
        (504, ErrorClass.RETRYABLE),
        (429, ErrorClass.RATE_LIMIT),
        (400, ErrorClass.CLIENT_FATAL),
        (404, ErrorClass.CLIENT_FATAL),
        (422, ErrorClass.CLIENT_FATAL),
    ],
)
def test_classify_status_codes(status: int, expected: ErrorClass) -> None:
    assert classify(status, body=None) is expected


def test_classify_oom_in_body_is_catastrophic() -> None:
    body = {"error": {"type": "OOM", "message": "CUDA out of memory"}}
    assert classify(500, body=body) is ErrorClass.CATASTROPHIC


def test_classify_malformed_json_is_catastrophic() -> None:
    assert classify(None, body=None, malformed=True) is ErrorClass.CATASTROPHIC
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/shared/inference/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'shared.inference'`.

- [ ] **Step 3: Implement `errors.py`**

`shared/inference/__init__.py`:

```python
"""OpenAI-compatible inference client and error handling."""

from shared.inference.client import InferenceClient
from shared.inference.errors import ErrorClass, InferenceError

__all__ = ["InferenceClient", "ErrorClass", "InferenceError"]
```

`shared/inference/errors.py`:

```python
"""Error classification for the inference client.

Four buckets, per spec §1:
- RETRYABLE: 5xx-class server errors, connection errors → exponential backoff
- RATE_LIMIT: 429 → backoff with Retry-After honor
- CLIENT_FATAL: 4xx where retry won't help → fail this example, continue campaign
- CATASTROPHIC: unrecoverable (OOM-in-body, malformed JSON, repeated 5xx) → halt campaign
"""
from __future__ import annotations

import enum
from typing import Mapping, Any


class ErrorClass(str, enum.Enum):
    RETRYABLE = "retryable"
    RATE_LIMIT = "rate_limit"
    CLIENT_FATAL = "client_fatal"
    CATASTROPHIC = "catastrophic"


class InferenceError(Exception):
    def __init__(self, msg: str, error_class: ErrorClass, status: int | None,
                 body: Any | None) -> None:
        super().__init__(msg)
        self.error_class = error_class
        self.status = status
        self.body = body


_OOM_TOKENS = ("OOM", "out of memory", "CUDA out of memory")


def classify(
    status: int | None,
    body: Mapping[str, Any] | None,
    malformed: bool = False,
) -> ErrorClass:
    if malformed:
        return ErrorClass.CATASTROPHIC
    if body is not None:
        msg = str(body.get("error", {}).get("message", "")) if isinstance(body, dict) else ""
        if any(token in msg for token in _OOM_TOKENS):
            return ErrorClass.CATASTROPHIC
    if status is None:
        return ErrorClass.CATASTROPHIC
    if status == 429:
        return ErrorClass.RATE_LIMIT
    if 500 <= status < 600:
        return ErrorClass.RETRYABLE
    if 400 <= status < 500:
        return ErrorClass.CLIENT_FATAL
    raise ValueError(f"unexpected status: {status}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/shared/inference/test_errors.py -v`
Expected: all parametrized cases pass.

- [ ] **Step 5: Write the retry helper**

`shared/inference/retry.py`:

```python
"""Exponential backoff loop for retryable errors."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# Spec §1: 3 retries with backoff 1s / 4s / 16s for retryable; 10/30/60s for rate-limit.
_RETRY_BACKOFFS_S = (1, 4, 16)
_RATE_LIMIT_BACKOFFS_S = (10, 30, 60)


def with_retry(
    call: Callable[[], T],
    is_retryable: Callable[[Exception], bool],
    is_rate_limit: Callable[[Exception], bool] = lambda _: False,
    retry_after_s: Callable[[Exception], float | None] = lambda _: None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Execute `call` with backoff retries for retryable/rate-limit errors."""
    last_exc: Exception | None = None
    for attempt in range(4):  # 1 try + 3 retries
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 — caller classifies
            last_exc = exc
            if attempt == 3:
                break
            if is_rate_limit(exc):
                wait = retry_after_s(exc) or _RATE_LIMIT_BACKOFFS_S[attempt]
            elif is_retryable(exc):
                wait = _RETRY_BACKOFFS_S[attempt]
            else:
                raise
            sleep(wait)
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 6: Write the failing client test**

`tests/shared/inference/test_client.py`:

```python
"""InferenceClient happy-path and error-path tests (HTTP layer mocked)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from shared.inference.client import InferenceClient, ChatRequest, Message
from shared.inference.errors import ErrorClass, InferenceError


@patch("shared.inference.client.requests.post")
def test_chat_completion_happy_path(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "chatcmpl-x",
        "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    }
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    resp = client.chat(ChatRequest(messages=[Message(role="user", content="hi")],
                                   temperature=0.0, top_p=1.0, max_tokens=8))
    assert resp.content == "hi"
    assert resp.usage.prompt_tokens == 5
    assert resp.usage.completion_tokens == 1


@patch("shared.inference.client.requests.post")
def test_chat_completion_4xx_raises_client_fatal(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = {
        "error": {"type": "invalid_request", "message": "bad input"}
    }
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    with pytest.raises(InferenceError) as ei:
        client.chat(ChatRequest(messages=[Message(role="user", content="x")],
                                temperature=0.0, top_p=1.0, max_tokens=8))
    assert ei.value.error_class is ErrorClass.CLIENT_FATAL


@patch("shared.inference.client.time.sleep")
@patch("shared.inference.client.requests.post")
def test_chat_completion_retries_then_succeeds(
    mock_post: MagicMock, mock_sleep: MagicMock
) -> None:
    # first two attempts return 503, third returns 200
    mock_post.side_effect = [
        MagicMock(status_code=503, json=MagicMock(return_value={"error": {"message": "tmp"}})),
        MagicMock(status_code=503, json=MagicMock(return_value={"error": {"message": "tmp"}})),
        MagicMock(status_code=200, json=MagicMock(return_value={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })),
    ]
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    resp = client.chat(ChatRequest(messages=[Message(role="user", content="x")],
                                   temperature=0.0, top_p=1.0, max_tokens=8))
    assert resp.content == "ok"
    assert mock_sleep.call_count == 2
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `uv run pytest tests/shared/inference/test_client.py -v`
Expected: `ImportError: cannot import name 'InferenceClient' from 'shared.inference.client'`.

- [ ] **Step 8: Implement the client**

`shared/inference/client.py`:

```python
"""OpenAI-compatible inference client.

Single class: `InferenceClient(endpoint, model, timeout_s)`. Two methods:
`chat()` and `embeddings()`. Errors classified per `shared.inference.errors`.

Per spec §1: non-streaming only; sovereign concerns live in the runner, not here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import requests

from shared.inference.errors import ErrorClass, InferenceError, classify
from shared.inference.retry import with_retry


@dataclass(frozen=True)
class Message:
    role: str   # system | user | assistant
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: list[Message]
    temperature: float
    top_p: float
    max_tokens: int
    seed: int | None = None
    logprobs: bool = False
    top_logprobs: int | None = None
    stop: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ChatResponse:
    content: str
    usage: Usage
    raw: Mapping[str, Any]   # full OpenAI response for storage


class InferenceClient:
    """Stateless OpenAI-compatible client. One instance per (endpoint, model)."""

    def __init__(self, endpoint: str, model: str, timeout_s: float) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def chat(self, req: ChatRequest) -> ChatResponse:
        body = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in req.messages],
            "temperature": req.temperature,
            "top_p": req.top_p,
            "max_tokens": req.max_tokens,
        }
        if req.seed is not None:
            body["seed"] = req.seed
        if req.logprobs:
            body["logprobs"] = True
            if req.top_logprobs is not None:
                body["top_logprobs"] = req.top_logprobs
        if req.stop:
            body["stop"] = req.stop

        url = f"{self.endpoint}/chat/completions"
        return with_retry(
            lambda: self._post_chat(url, body),
            is_retryable=lambda e: isinstance(e, InferenceError)
                                   and e.error_class is ErrorClass.RETRYABLE,
            is_rate_limit=lambda e: isinstance(e, InferenceError)
                                    and e.error_class is ErrorClass.RATE_LIMIT,
            retry_after_s=lambda e: (
                float(e.body["retry_after"])
                if isinstance(e, InferenceError) and isinstance(e.body, dict)
                and "retry_after" in e.body
                else None
            ),
        )

    def _post_chat(self, url: str, body: Mapping[str, Any]) -> ChatResponse:
        try:
            resp = requests.post(url, json=body, timeout=self.timeout_s)
        except requests.RequestException as e:
            raise InferenceError(str(e), ErrorClass.RETRYABLE, None, None) from e
        return self._parse_chat(resp)

    @staticmethod
    def _parse_chat(resp: "requests.Response") -> ChatResponse:
        try:
            body = resp.json()
        except ValueError as e:
            raise InferenceError("malformed json", ErrorClass.CATASTROPHIC,
                                 resp.status_code, None) from e
        if resp.status_code != 200:
            cls = classify(resp.status_code, body)
            raise InferenceError(
                f"http {resp.status_code}: {body.get('error', {}).get('message', '')}",
                cls, resp.status_code, body,
            )
        choice = body["choices"][0]["message"]["content"]
        u = body.get("usage", {}) or {}
        usage = Usage(
            prompt_tokens=int(u.get("prompt_tokens", 0)),
            completion_tokens=int(u.get("completion_tokens", 0)),
            total_tokens=int(u.get("total_tokens", 0)),
        )
        return ChatResponse(content=choice, usage=usage, raw=body)
```

- [ ] **Step 9: Run all inference tests to verify they pass**

Run: `uv run pytest tests/shared/inference/ -v`
Expected: all pass (errors: 8 cases + client: 3 cases = 11 passed).

- [ ] **Step 10: Commit**

```bash
git add shared/inference/ tests/shared/inference/
git commit -m "Add shared/inference/: InferenceClient + 4-bucket error classification

Per spec §1: pure OpenAI-compatible wire, non-streaming, exponential backoff
for retryable (1/4/16s) and rate-limit (10/30/60s).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `shared/models/` — ModelManifest + YAML registry + Postgres sync

**Files:**
- Create: `shared/models/__init__.py`
- Create: `shared/models/manifest.py`
- Create: `shared/models/registry.py`
- Create: `tests/shared/models/__init__.py`
- Create: `tests/shared/models/test_manifest.py`
- Create: `tests/shared/models/test_registry.py`

- [ ] **Step 1: Write the failing manifest test**

`tests/shared/models/__init__.py`:

```python
```

`tests/shared/models/test_manifest.py`:

```python
"""Tests for the ModelManifest pydantic model + YAML loading."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from shared.models.manifest import ModelManifest, load_manifest_yaml


def test_load_minimal_manifest(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: qwen2.5-0.5b-instruct-ollama
        family: qwen2.5
        size: 0.5b
        revision: "2024-09-19"
        quantization: null
        runtime: ollama
        runtime_version: "0.3.12"
        target_host: mac
        endpoint: "http://localhost:11434/v1"
        capabilities: [chat, embeddings]
        context_window: 32768
        default_sampling:
            temperature: 0.0
            top_p: 1.0
            max_tokens: 256
    """))
    m = load_manifest_yaml(yaml_path)
    assert m.id == "qwen2.5-0.5b-instruct-ollama"
    assert m.runtime == "ollama"
    assert m.context_window == 32768
    assert m.default_sampling.max_tokens == 256
    assert "chat" in m.capabilities


def test_unknown_runtime_rejected(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: x
        family: x
        size: x
        revision: "x"
        runtime: faketime
        runtime_version: x
        target_host: mac
        endpoint: x
        capabilities: []
        context_window: 1
        default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 1}
    """))
    with pytest.raises(ValueError, match="runtime"):
        load_manifest_yaml(yaml_path)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/shared/models/test_manifest.py -v`
Expected: `ModuleNotFoundError: No module named 'shared.models'`.

- [ ] **Step 3: Implement the manifest model**

`shared/models/__init__.py`:

```python
"""Model registry: YAML manifests resolved to typed records and synced to Postgres."""

from shared.models.manifest import ModelManifest, Sampling, load_manifest_yaml
from shared.models.registry import sync_to_postgres, resolve

__all__ = [
    "ModelManifest",
    "Sampling",
    "load_manifest_yaml",
    "sync_to_postgres",
    "resolve",
]
```

`shared/models/manifest.py`:

```python
"""Typed `ModelManifest` plus YAML loader.

The manifest is the descriptor that makes a run replayable. It captures
just enough to reproduce a run in practice: model id + revision/quant +
runtime + version + sampling + target host. Per spec §1 ("pragmatic" rigor).
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

ALLOWED_RUNTIMES = {"ollama", "vllm", "vllm_metal", "nim", "trt_llm", "mlx", "sglang"}
ALLOWED_CAPABILITIES = {"chat", "embeddings", "seed", "logprobs"}


class Sampling(BaseModel):
    temperature: float
    top_p: float
    max_tokens: int


class ModelManifest(BaseModel):
    id: str
    family: str
    size: str
    revision: str
    quantization: str | None = None
    runtime: str
    runtime_version: str
    target_host: Literal["mac", "spark", "cloud-burst-a3", "cloud-burst-p5"]
    endpoint: str
    capabilities: list[str] = Field(default_factory=list)
    context_window: int
    default_sampling: Sampling

    @field_validator("runtime")
    @classmethod
    def _runtime_known(cls, v: str) -> str:
        if v not in ALLOWED_RUNTIMES:
            raise ValueError(
                f"runtime {v!r} not in {sorted(ALLOWED_RUNTIMES)}"
            )
        return v

    @field_validator("capabilities")
    @classmethod
    def _capabilities_known(cls, v: list[str]) -> list[str]:
        unknown = set(v) - ALLOWED_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capabilities: {sorted(unknown)}")
        return v


def load_manifest_yaml(path: Path) -> ModelManifest:
    raw = yaml.safe_load(path.read_text())
    return ModelManifest.model_validate(raw)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/shared/models/test_manifest.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write the registry sync test**

`tests/shared/models/test_registry.py`:

```python
"""Tests for the Postgres-sync side of the model registry."""
from __future__ import annotations

import textwrap
from pathlib import Path

from shared.db.connection import connect
from shared.db.migrations import apply_all
from shared.models.manifest import load_manifest_yaml
from shared.models.registry import sync_to_postgres, resolve


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    apply_all(test=True)


def _write_manifest(path: Path) -> Path:
    path.write_text(textwrap.dedent("""\
        id: qwen2.5-0.5b-instruct-ollama
        family: qwen2.5
        size: 0.5b
        revision: "2024-09-19"
        runtime: ollama
        runtime_version: "0.3.12"
        target_host: mac
        endpoint: "http://localhost:11434/v1"
        capabilities: [chat]
        context_window: 32768
        default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 256}
    """))
    return path


def test_sync_to_postgres_inserts_row(tmp_path: Path) -> None:
    _reset_test_db()
    yaml_path = _write_manifest(tmp_path / "m.yaml")
    m = load_manifest_yaml(yaml_path)
    sync_to_postgres([m], test=True)
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, runtime FROM model_manifest")
        rows = cur.fetchall()
    assert rows == [("qwen2.5-0.5b-instruct-ollama", "ollama")]


def test_resolve_returns_manifest_by_id(tmp_path: Path) -> None:
    _reset_test_db()
    yaml_path = _write_manifest(tmp_path / "m.yaml")
    sync_to_postgres([load_manifest_yaml(yaml_path)], test=True)
    m = resolve("qwen2.5-0.5b-instruct-ollama", test=True)
    assert m.runtime == "ollama"
    assert m.endpoint.endswith("/v1")
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `uv run pytest tests/shared/models/test_registry.py -v`
Expected: `ImportError: cannot import name 'sync_to_postgres'`.

- [ ] **Step 7: Implement the registry**

`shared/models/registry.py`:

```python
"""Postgres-backed model registry: load YAMLs and sync into model_manifest."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import yaml

from shared.db.connection import connect
from shared.models.manifest import ModelManifest, load_manifest_yaml

REGISTRY_DIR = Path(__file__).resolve().parent / "registry"


def discover_yamls(directory: Path = REGISTRY_DIR) -> list[Path]:
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
    """Load every YAML under REGISTRY_DIR and sync. Returns count."""
    paths = discover_yamls()
    manifests = [load_manifest_yaml(p) for p in paths]
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
```

- [ ] **Step 8: Run all model tests to verify they pass**

Run: `uv run pytest tests/shared/models/ -v`
Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
git add shared/models/__init__.py shared/models/manifest.py shared/models/registry.py tests/shared/models/
git commit -m "Add shared/models/: typed ModelManifest + YAML loader + Postgres sync

Per spec §1: 'new revision = new id' convention enforced by the registry being
keyed on id; the loader validates runtime + capabilities against allow-lists.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: First model manifest YAML

**Files:**
- Create: `shared/models/registry/qwen2.5-0.5b-instruct-ollama.yaml`

- [ ] **Step 1: Pull the model locally**

Run: `ollama pull qwen2.5:0.5b-instruct`
Expected: download completes; `ollama list` shows the model.

(Prerequisite: Ollama installed via `brew install ollama && brew services start ollama`. Documented separately if not already present.)

- [ ] **Step 2: Verify the OpenAI-compatible endpoint works**

Run:
```bash
curl -s http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "qwen2.5:0.5b-instruct",
        "messages": [{"role": "user", "content": "say hi in one word"}],
        "temperature": 0.0,
        "max_tokens": 8
      }' | head -c 400
```
Expected: a JSON response with `choices[0].message.content` containing a short string. Note Ollama uses `model: "qwen2.5:0.5b-instruct"` (with the colon — Ollama's tag syntax), which is *different* from our registry id (which uses dashes). That mapping happens in the manifest's `id` field for our purposes; the wire `model` field uses the registry id, and our manifest's `endpoint` points to a server configured to accept it. For Ollama we set `id` to match the Ollama tag exactly to avoid translation: `id: "qwen2.5:0.5b-instruct"`.

- [ ] **Step 3: Write the manifest**

`shared/models/registry/qwen2.5-0.5b-instruct-ollama.yaml`:

```yaml
# Smallest Qwen 2.5 Instruct model, served via Ollama on the Mac mini.
# Used by experiment 0001-inference-contract-validation to smoke-test the substrate.

id: "qwen2.5:0.5b-instruct"
family: qwen2.5
size: 0.5b
revision: "2024-09-19"       # Qwen 2.5 family release date pinned
quantization: null            # Ollama's default tag is unquantized for this model
runtime: ollama
runtime_version: "0.3.12"
target_host: mac
endpoint: "http://localhost:11434/v1"
capabilities: [chat]
context_window: 32768
default_sampling:
  temperature: 0.0
  top_p: 1.0
  max_tokens: 256
```

- [ ] **Step 4: Sync into Postgres**

Run: `uv run python -c "from shared.models.registry import sync_all; print('synced:', sync_all())"`
Expected: `synced: 1`.

- [ ] **Step 5: Verify with `resolve`**

Run: `uv run python -c "from shared.models.registry import resolve; m = resolve('qwen2.5:0.5b-instruct'); print(m.endpoint, m.context_window)"`
Expected: `http://localhost:11434/v1 32768`.

- [ ] **Step 6: Commit**

```bash
git add shared/models/registry/qwen2.5-0.5b-instruct-ollama.yaml
git commit -m "Register qwen2.5:0.5b-instruct (Ollama, Mac) as first model manifest

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `shared/eval/cost/` — rate-card YAML + cost calculator

**Files:**
- Create: `shared/eval/__init__.py`
- Create: `shared/eval/cost/__init__.py`
- Create: `shared/eval/cost/accountant.py`
- Create: `shared/eval/cost/rate_cards/mac-mini.yaml`
- Create: `tests/shared/eval/__init__.py`
- Create: `tests/shared/eval/test_cost.py`

- [ ] **Step 1: Write the failing cost test**

`tests/shared/eval/__init__.py`:

```python
```

`tests/shared/eval/test_cost.py`:

```python
"""Tests for the cost accountant."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.eval.cost.accountant import CostAccountant, RateCard


def test_per_token_cost_calculation() -> None:
    rc = RateCard(
        target_host="mac",
        unit="per_mtok",
        prompt_usd_per_mtok=0.0,
        completion_usd_per_mtok=0.0,
        wall_usd_per_hour=0.05,
    )
    cost = CostAccountant.from_rate_card(rc).cost_per_call(
        prompt_tokens=1_000, completion_tokens=500, wall_ms=400
    )
    # Mac mini is free-per-token (amortized) but bill 0.05 USD/hour wall time → 400ms → 0.05 * (0.4/3600).
    assert cost == pytest.approx(0.05 * 0.4 / 3600, rel=1e-6)


def test_per_mtok_cost_calculation() -> None:
    rc = RateCard(
        target_host="tier2-fireworks",
        unit="per_mtok",
        prompt_usd_per_mtok=0.20,
        completion_usd_per_mtok=0.60,
        wall_usd_per_hour=0.0,
    )
    cost = CostAccountant.from_rate_card(rc).cost_per_call(
        prompt_tokens=1_000_000, completion_tokens=500_000, wall_ms=10_000
    )
    assert cost == pytest.approx(0.20 + 0.30, rel=1e-6)


def test_missing_usage_falls_back_to_wall_time() -> None:
    rc = RateCard(
        target_host="mac",
        unit="per_mtok",
        prompt_usd_per_mtok=0.10,
        completion_usd_per_mtok=0.10,
        wall_usd_per_hour=0.05,
    )
    cost = CostAccountant.from_rate_card(rc).cost_per_call(
        prompt_tokens=None, completion_tokens=None, wall_ms=3_600_000
    )
    assert cost == pytest.approx(0.05, rel=1e-6)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/shared/eval/test_cost.py -v`
Expected: `ModuleNotFoundError: No module named 'shared.eval'`.

- [ ] **Step 3: Implement the cost accountant**

`shared/eval/__init__.py`:

```python
"""Evaluation runner, cost, judges."""
```

`shared/eval/cost/__init__.py`:

```python
"""Cost accountant: rate-card math; one pure function per call."""

from shared.eval.cost.accountant import CostAccountant, RateCard, load_rate_card

__all__ = ["CostAccountant", "RateCard", "load_rate_card"]
```

`shared/eval/cost/accountant.py`:

```python
"""Rate-card-based cost accountant.

Pure function from (usage, wall_ms) → cost_usd. Per spec §1: cost lives in the
runner; the contract is unaware. Rate cards are per `target_host`, loaded from
YAML files under `rate_cards/`.

For each call:
    if usage is present:
        cost = (prompt_tokens × prompt_usd_per_mtok + completion_tokens × completion_usd_per_mtok) / 1e6
               + wall_ms × wall_usd_per_hour / 3_600_000
    else:
        cost = wall_ms × wall_usd_per_hour / 3_600_000     (fallback)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

RATE_CARDS_DIR = Path(__file__).resolve().parent / "rate_cards"


@dataclass(frozen=True)
class RateCard:
    target_host: str
    unit: Literal["per_mtok"]   # only one unit supported in v0.1
    prompt_usd_per_mtok: float
    completion_usd_per_mtok: float
    wall_usd_per_hour: float


def load_rate_card(target_host: str) -> RateCard:
    path = RATE_CARDS_DIR / f"{target_host}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"no rate card for target_host={target_host!r} at {path}"
        )
    raw = yaml.safe_load(path.read_text())
    return RateCard(**raw)


class CostAccountant:
    def __init__(self, rate_card: RateCard) -> None:
        self.rate_card = rate_card

    @classmethod
    def from_rate_card(cls, rate_card: RateCard) -> "CostAccountant":
        return cls(rate_card)

    @classmethod
    def for_target(cls, target_host: str) -> "CostAccountant":
        return cls(load_rate_card(target_host))

    def cost_per_call(
        self,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        wall_ms: int,
    ) -> float:
        wall_cost = wall_ms * self.rate_card.wall_usd_per_hour / 3_600_000
        if prompt_tokens is None or completion_tokens is None:
            return wall_cost
        token_cost = (
            prompt_tokens * self.rate_card.prompt_usd_per_mtok
            + completion_tokens * self.rate_card.completion_usd_per_mtok
        ) / 1_000_000
        return token_cost + wall_cost
```

- [ ] **Step 4: Write the Mac-mini rate card**

`shared/eval/cost/rate_cards/mac-mini.yaml`:

```yaml
# Mac mini M4 — sovereign, always-on. Token cost is effectively zero
# (amortized hardware cost is so small per token it's not worth tracking
# at micro-cent precision); we track wall-time at a nominal $0.05/hour
# so cost-vs-cloud comparisons in Phase 8 have a real number to compare.

target_host: mac
unit: per_mtok
prompt_usd_per_mtok: 0.0
completion_usd_per_mtok: 0.0
wall_usd_per_hour: 0.05
```

- [ ] **Step 5: Run all cost tests to verify they pass**

Run: `uv run pytest tests/shared/eval/test_cost.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add shared/eval/__init__.py shared/eval/cost/ tests/shared/eval/__init__.py tests/shared/eval/test_cost.py
git commit -m "Add shared/eval/cost/: rate cards + cost accountant + mac-mini card

Per spec §1: cost lives in the runner; pure (usage, wall_ms) → cost_usd.
Wall-time fallback when usage is absent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Seed gold set + JSONL schema

**Files:**
- Create: `experiments/0001-inference-contract-validation/seed.jsonl`
- Create: `experiments/0001-inference-contract-validation/prompt_templates/general/multi-choice.j2`

- [ ] **Step 1: Create the experiment folder**

Run:
```bash
mkdir -p experiments/0001-inference-contract-validation/prompt_templates/general
mkdir -p experiments/0001-inference-contract-validation/results
```

- [ ] **Step 2: Write the Jinja template**

`experiments/0001-inference-contract-validation/prompt_templates/general/multi-choice.j2`:

```jinja
You will be asked a multiple-choice question. Reply with a single letter — A, B, C, or D — and nothing else.

Question: {{ question }}

Options:
A. {{ choices.A }}
B. {{ choices.B }}
C. {{ choices.C }}
D. {{ choices.D }}

Answer:
```

- [ ] **Step 3: Write the seed JSONL (3 examples, all public-derived)**

`experiments/0001-inference-contract-validation/seed.jsonl`:

```jsonl
{"example_id": "ex_general_seed0001", "lane": "general", "source": "hand-authored smoke-test seed", "annotator": "jonathan", "annotated_at": "2026-05-26", "prompt_template": "general/multi-choice.j2", "inputs": {"question": "What is 2 + 2?", "choices": {"A": "3", "B": "4", "C": "5", "D": "22"}}, "expected": {"type": "exact", "value": "B"}, "provenance_tag": "public", "never_to_third_party": false, "tags": ["arithmetic", "smoke"], "contamination_risk": "high"}
{"example_id": "ex_general_seed0002", "lane": "general", "source": "hand-authored smoke-test seed", "annotator": "jonathan", "annotated_at": "2026-05-26", "prompt_template": "general/multi-choice.j2", "inputs": {"question": "The capital of Japan is which city?", "choices": {"A": "Osaka", "B": "Kyoto", "C": "Tokyo", "D": "Nara"}}, "expected": {"type": "exact", "value": "C"}, "provenance_tag": "public", "never_to_third_party": false, "tags": ["geography", "smoke"], "contamination_risk": "high"}
{"example_id": "ex_general_seed0003", "lane": "general", "source": "hand-authored smoke-test seed", "annotator": "jonathan", "annotated_at": "2026-05-26", "prompt_template": "general/multi-choice.j2", "inputs": {"question": "Which sequence is in ascending order?", "choices": {"A": "5, 3, 1", "B": "1, 5, 3", "C": "3, 1, 5", "D": "1, 3, 5"}}, "expected": {"type": "exact", "value": "D"}, "provenance_tag": "public", "never_to_third_party": false, "tags": ["ordering", "smoke"], "contamination_risk": "high"}
```

Each example uses `example_id` that fits the spec's `ex_<lane>_<8-hex>` convention; here `seed0001`/`seed0002`/`seed0003` are used as readable placeholders for the smoke-test seed. Production examples will use real uuid4-derived 8-hex suffixes.

- [ ] **Step 4: Commit**

```bash
git add experiments/0001-inference-contract-validation/seed.jsonl experiments/0001-inference-contract-validation/prompt_templates/
git commit -m "Add 3-example smoke-test seed (public) for experiment 0001

Hand-authored multi-choice examples wired through a tiny Jinja template.
Used to validate the contract substrate end-to-end on the Mac mini.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `shared/goldsets/` — JSONL schema + Jinja rendering + idempotent loader

**Files:**
- Create: `shared/goldsets/__init__.py`
- Create: `shared/goldsets/schema.py`
- Create: `shared/goldsets/render.py`
- Create: `shared/goldsets/loader.py`
- Create: `tests/shared/goldsets/__init__.py`
- Create: `tests/shared/goldsets/test_schema.py`
- Create: `tests/shared/goldsets/test_render.py`
- Create: `tests/shared/goldsets/test_loader.py`

- [ ] **Step 1: Write the failing schema test**

`tests/shared/goldsets/__init__.py`:

```python
```

`tests/shared/goldsets/test_schema.py`:

```python
"""Tests for the gold-set JSONL record schema."""
from __future__ import annotations

import pytest

from shared.goldsets.schema import GoldExample


def test_valid_exact_example_parses() -> None:
    raw = {
        "example_id": "ex_general_001a2b3c",
        "lane": "general",
        "source": "src",
        "annotator": "jonathan",
        "annotated_at": "2026-05-26",
        "prompt_template": "general/multi-choice.j2",
        "inputs": {"question": "q", "choices": {"A": "a", "B": "b"}},
        "expected": {"type": "exact", "value": "A"},
        "provenance_tag": "public",
        "never_to_third_party": False,
        "tags": ["smoke"],
        "contamination_risk": "high",
    }
    ex = GoldExample.model_validate(raw)
    assert ex.expected.type == "exact"
    assert ex.expected.value == "A"


def test_unknown_lane_rejected() -> None:
    with pytest.raises(ValueError, match="lane"):
        GoldExample.model_validate({
            "example_id": "ex_x_001a2b3c",
            "lane": "marsupials",
            "annotator": "x",
            "annotated_at": "2026-05-26",
            "prompt_template": "x.j2",
            "inputs": {},
            "expected": {"type": "exact", "value": "A"},
            "provenance_tag": "public",
            "never_to_third_party": False,
        })


def test_id_format_enforced() -> None:
    with pytest.raises(ValueError, match="example_id"):
        GoldExample.model_validate({
            "example_id": "invalid-id-format",
            "lane": "general",
            "annotator": "x",
            "annotated_at": "2026-05-26",
            "prompt_template": "x.j2",
            "inputs": {},
            "expected": {"type": "exact", "value": "A"},
            "provenance_tag": "public",
            "never_to_third_party": False,
        })
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/shared/goldsets/test_schema.py -v`
Expected: `ModuleNotFoundError: No module named 'shared.goldsets'`.

- [ ] **Step 3: Implement the schema**

`shared/goldsets/__init__.py`:

```python
"""Gold-set JSONL schema, prompt rendering, and idempotent Postgres loader."""

from shared.goldsets.schema import (
    GoldExample,
    Expected,
    ALLOWED_LANES,
    ALLOWED_EXPECTED_TYPES,
)
from shared.goldsets.render import render_prompt
from shared.goldsets.loader import load_jsonl_to_postgres

__all__ = [
    "GoldExample",
    "Expected",
    "ALLOWED_LANES",
    "ALLOWED_EXPECTED_TYPES",
    "render_prompt",
    "load_jsonl_to_postgres",
]
```

`shared/goldsets/schema.py`:

```python
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
```

- [ ] **Step 4: Run the schema test to verify it passes**

Run: `uv run pytest tests/shared/goldsets/test_schema.py -v`
Expected: 3 passed.

- [ ] **Step 5: Write the failing render test**

`tests/shared/goldsets/test_render.py`:

```python
"""Tests for deterministic prompt rendering."""
from __future__ import annotations

import textwrap
from pathlib import Path

from shared.goldsets.render import render_prompt


def test_render_simple_template(tmp_path: Path) -> None:
    tpl_dir = tmp_path / "general"
    tpl_dir.mkdir()
    (tpl_dir / "multi-choice.j2").write_text(textwrap.dedent("""\
        Q: {{ question }}
        A. {{ choices.A }}
        B. {{ choices.B }}
    """))
    out = render_prompt(
        template_root=tmp_path,
        template_path="general/multi-choice.j2",
        inputs={"question": "x?", "choices": {"A": "yes", "B": "no"}},
    )
    assert out == "Q: x?\nA. yes\nB. no\n"


def test_render_is_deterministic(tmp_path: Path) -> None:
    tpl_dir = tmp_path / "general"
    tpl_dir.mkdir()
    (tpl_dir / "t.j2").write_text("{{ a }} | {{ b }}")
    inputs = {"a": "x", "b": "y"}
    assert render_prompt(tmp_path, "general/t.j2", inputs) == \
           render_prompt(tmp_path, "general/t.j2", inputs)
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `uv run pytest tests/shared/goldsets/test_render.py -v`
Expected: `ImportError: cannot import name 'render_prompt'`.

- [ ] **Step 7: Implement `render.py`**

`shared/goldsets/render.py`:

```python
"""Deterministic Jinja2 prompt rendering.

The renderer is stateless and pure: same template + same inputs → same output.
StrictUndefined ensures missing fields raise rather than silently empty.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def render_prompt(
    template_root: Path,
    template_path: str,
    inputs: dict[str, Any],
) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_root)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    tpl = env.get_template(template_path)
    return tpl.render(**inputs)
```

- [ ] **Step 8: Run the render test to verify it passes**

Run: `uv run pytest tests/shared/goldsets/test_render.py -v`
Expected: 2 passed.

- [ ] **Step 9: Write the failing loader test**

`tests/shared/goldsets/test_loader.py`:

```python
"""Tests for the JSONL → Postgres loader (idempotency + immutability)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.db.connection import connect
from shared.db.migrations import apply_all
from shared.goldsets.loader import load_jsonl_to_postgres


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    apply_all(test=True)


SEED = [
    {"example_id": "ex_general_seed0001", "lane": "general",
     "source": "x", "annotator": "j", "annotated_at": "2026-05-26",
     "prompt_template": "general/multi-choice.j2",
     "inputs": {"question": "q", "choices": {"A": "a", "B": "b"}},
     "expected": {"type": "exact", "value": "A"},
     "provenance_tag": "public", "never_to_third_party": False,
     "tags": ["smoke"], "contamination_risk": "high"}
]


def _write_seed(p: Path) -> None:
    with p.open("w") as f:
        for rec in SEED:
            f.write(json.dumps(rec) + "\n")


def test_load_writes_one_version_and_one_example(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(
        jsonl_path=p, version="v0.1", git_commit_sha="abc123",
        test=True,
    )
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version, released FROM gold_set_version")
        assert cur.fetchall() == [("v0.1", True)]
        cur.execute("SELECT example_id FROM gold_example")
        assert cur.fetchall() == [(pytest.approx_uuid_str(SEED[0]["example_id"], if_uuid=False),)] if hasattr(pytest, "approx_uuid_str") else cur.fetchall()


def test_load_is_idempotent_on_same_sha(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)  # second call no-op
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM gold_example")
        assert cur.fetchone() == (1,)


def test_load_rejects_same_version_different_sha(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)
    with pytest.raises(ValueError, match="immutability"):
        load_jsonl_to_postgres(p, "v0.1", "def456", test=True)
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `uv run pytest tests/shared/goldsets/test_loader.py -v`
Expected: `ImportError: cannot import name 'load_jsonl_to_postgres'`.

- [ ] **Step 11: Implement the loader**

`shared/goldsets/loader.py`:

```python
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
    """Returns the number of examples loaded (0 if no-op)."""
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
            examples.append(GoldExample.model_validate(raw))

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
```

- [ ] **Step 12: Simplify the schema test that referenced a non-existent pytest helper**

Edit `tests/shared/goldsets/test_loader.py` `test_load_writes_one_version_and_one_example`: replace the `pytest.approx_uuid_str` line with a direct expected-row check:

```python
def test_load_writes_one_version_and_one_example(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version, released FROM gold_set_version")
        assert cur.fetchall() == [("v0.1", True)]
        cur.execute("SELECT count(*) FROM gold_example")
        assert cur.fetchone() == (1,)
```

- [ ] **Step 13: Run all goldset tests to verify they pass**

Run: `uv run pytest tests/shared/goldsets/ -v`
Expected: 7 passed.

- [ ] **Step 14: Load the smoke seed into production Postgres**

Run:
```bash
uv run python -c "
from pathlib import Path
from shared.goldsets.loader import load_jsonl_to_postgres
n = load_jsonl_to_postgres(
    Path('experiments/0001-inference-contract-validation/seed.jsonl'),
    version='smoke-v0.0',
    git_commit_sha='wip-smoke',
)
print('loaded', n, 'examples')
"
```
Expected: `loaded 3 examples` (or `loaded 0 examples` on rerun — idempotent).

- [ ] **Step 15: Commit**

```bash
git add shared/goldsets/ tests/shared/goldsets/
git commit -m "Add shared/goldsets/: schema + Jinja renderer + idempotent Postgres loader

Per spec §3: JSONL records validated against the pydantic schema; loader is
idempotent on (version, sha) and refuses inconsistent re-release.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: `shared/eval/judges/` — deterministic judge + aggregation + bundle YAML

**Files:**
- Create: `shared/eval/judges/__init__.py`
- Create: `shared/eval/judges/deterministic.py`
- Create: `shared/eval/judges/aggregate.py`
- Create: `shared/eval/judges/configs/v0.1.yaml`
- Create: `tests/shared/eval/test_deterministic.py`
- Create: `tests/shared/eval/test_aggregate.py`

- [ ] **Step 1: Write the failing deterministic-judge test**

`tests/shared/eval/test_deterministic.py`:

```python
"""Tests for the deterministic judge (exact + set matching with normalization)."""
from __future__ import annotations

import pytest

from shared.eval.judges.deterministic import score, DeterministicConfig
from shared.goldsets.schema import Expected


@pytest.fixture
def cfg() -> DeterministicConfig:
    return DeterministicConfig(
        string_normalize=["lowercase", "strip_punct", "whitespace_collapse"],
        numeric_tolerance_abs=1e-6,
        numeric_tolerance_rel=1e-3,
    )


def test_exact_string_match_after_normalization(cfg: DeterministicConfig) -> None:
    assert score(response="  B.", expected=Expected(type="exact", value="B"), cfg=cfg) == 1.0
    assert score(response="b", expected=Expected(type="exact", value="B"), cfg=cfg) == 1.0
    assert score(response="C", expected=Expected(type="exact", value="B"), cfg=cfg) == 0.0


def test_exact_numeric_match_within_tolerance(cfg: DeterministicConfig) -> None:
    assert score(response="3.14159", expected=Expected(type="exact", value=3.14159), cfg=cfg) == 1.0
    assert score(response="3.142", expected=Expected(type="exact", value=3.14159), cfg=cfg) == 1.0
    assert score(response="3.0", expected=Expected(type="exact", value=3.14159), cfg=cfg) == 0.0


def test_set_match_uses_f1(cfg: DeterministicConfig) -> None:
    # Two of three correct + one extra → precision 2/3, recall 2/3 → F1 = 2/3
    result = score(
        response="apple, banana, durian",
        expected=Expected(type="set", value=["apple", "banana", "cherry"]),
        cfg=cfg,
    )
    assert result == pytest.approx(2 / 3, rel=1e-3)


def test_unsupported_expected_type_raises(cfg: DeterministicConfig) -> None:
    with pytest.raises(ValueError, match="rubric"):
        score(response="x", expected=Expected(type="rubric", value={"rubric_id": "r"}), cfg=cfg)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/shared/eval/test_deterministic.py -v`
Expected: `ModuleNotFoundError: No module named 'shared.eval.judges'`.

- [ ] **Step 3: Implement the deterministic judge**

`shared/eval/judges/__init__.py`:

```python
"""Judge plumbing: deterministic scorer + aggregation across judges."""

from shared.eval.judges.deterministic import score as deterministic_score, DeterministicConfig
from shared.eval.judges.aggregate import aggregate, Judgement

__all__ = ["deterministic_score", "DeterministicConfig", "aggregate", "Judgement"]
```

`shared/eval/judges/deterministic.py`:

```python
"""Deterministic scorer for `expected.type ∈ {exact, set}`.

Normalization (configured per bundle): lowercase / strip_punct / whitespace_collapse.
Numeric comparison: absolute or relative tolerance.
Set comparison: F1 between predicted set (parsed from comma-separated response)
and expected set.

For `expected.type == "rubric"`, this scorer raises — rubric routing goes
through the specialist judge (Phase 3).
"""
from __future__ import annotations

import re
import string
from dataclasses import dataclass

from shared.goldsets.schema import Expected


@dataclass(frozen=True)
class DeterministicConfig:
    string_normalize: list[str]    # subset of {"lowercase", "strip_punct", "whitespace_collapse"}
    numeric_tolerance_abs: float
    numeric_tolerance_rel: float


_PUNCT_RE = re.compile(rf"[{re.escape(string.punctuation)}]")
_WS_RE = re.compile(r"\s+")


def _normalize(s: str, ops: list[str]) -> str:
    if "lowercase" in ops:
        s = s.lower()
    if "strip_punct" in ops:
        s = _PUNCT_RE.sub("", s)
    if "whitespace_collapse" in ops:
        s = _WS_RE.sub(" ", s).strip()
    return s


def _try_float(s: str) -> float | None:
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return None


def score(response: str, expected: Expected, cfg: DeterministicConfig) -> float:
    if expected.type == "rubric":
        raise ValueError("deterministic scorer cannot handle rubric type; route to specialist")

    if expected.type == "exact":
        # Numeric path
        if isinstance(expected.value, (int, float)):
            pred = _try_float(response)
            if pred is None:
                return 0.0
            target = float(expected.value)
            if abs(pred - target) <= cfg.numeric_tolerance_abs:
                return 1.0
            denom = abs(target) if target != 0 else 1.0
            return 1.0 if abs(pred - target) / denom <= cfg.numeric_tolerance_rel else 0.0
        # String path
        return 1.0 if _normalize(response, cfg.string_normalize) == \
                      _normalize(str(expected.value), cfg.string_normalize) else 0.0

    if expected.type == "set":
        expected_set = {_normalize(str(x), cfg.string_normalize) for x in expected.value}
        predicted_raw = [t.strip() for t in str(response).split(",") if t.strip()]
        predicted_set = {_normalize(t, cfg.string_normalize) for t in predicted_raw}
        if not predicted_set and not expected_set:
            return 1.0
        tp = len(predicted_set & expected_set)
        precision = tp / len(predicted_set) if predicted_set else 0.0
        recall = tp / len(expected_set) if expected_set else 0.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    raise ValueError(f"unsupported expected.type: {expected.type}")
```

- [ ] **Step 4: Run the deterministic test to verify it passes**

Run: `uv run pytest tests/shared/eval/test_deterministic.py -v`
Expected: 4 passed.

- [ ] **Step 5: Write the failing aggregation test**

`tests/shared/eval/test_aggregate.py`:

```python
"""Tests for judgement aggregation."""
from __future__ import annotations

import pytest

from shared.eval.judges.aggregate import Judgement, aggregate


def test_single_deterministic_judgement_wins() -> None:
    j = [Judgement(judge_role="deterministic", score=1.0, score_kind="binary")]
    out = aggregate(j, weights={"deterministic": 1.0, "specialist": 0.7})
    assert out == (1.0, "binary")


def test_deterministic_tie_breaks_when_multiple_judges_present() -> None:
    j = [
        Judgement(judge_role="deterministic", score=1.0, score_kind="binary"),
        Judgement(judge_role="specialist", score=0.4, score_kind="scalar"),
    ]
    out = aggregate(j, weights={"deterministic": 1.0, "specialist": 0.7})
    assert out == (1.0, "binary")


def test_weighted_mean_when_no_deterministic() -> None:
    j = [
        Judgement(judge_role="specialist", score=0.8, score_kind="scalar"),
        Judgement(judge_role="generalist", score=0.5, score_kind="scalar"),
    ]
    out = aggregate(j, weights={"specialist": 0.7, "generalist": 0.3})
    assert out[0] == pytest.approx((0.8 * 0.7 + 0.5 * 0.3) / 1.0, rel=1e-6)
    assert out[1] == "rubric_aggregate"


def test_parse_errors_excluded_from_aggregation() -> None:
    j = [
        Judgement(judge_role="specialist", score=None, score_kind="scalar", parse_error=True),
        Judgement(judge_role="generalist", score=0.5, score_kind="scalar"),
    ]
    out = aggregate(j, weights={"specialist": 0.7, "generalist": 0.3})
    assert out[0] == pytest.approx(0.5, rel=1e-6)
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `uv run pytest tests/shared/eval/test_aggregate.py -v`
Expected: `ImportError: cannot import name 'aggregate'`.

- [ ] **Step 7: Implement aggregation**

`shared/eval/judges/aggregate.py`:

```python
"""Aggregation rule (spec §4): deterministic tie-break, else weighted mean."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Judgement:
    judge_role: str         # deterministic | specialist | generalist | ...
    score: float | None     # None if parse_error
    score_kind: str         # binary | scalar | rubric_aggregate
    parse_error: bool = False


def aggregate(
    judgements: list[Judgement],
    weights: dict[str, float],
) -> tuple[float, str]:
    """Return (aggregated_score, score_kind).

    Raises ValueError if no usable judgement remains after excluding parse errors.
    """
    usable = [j for j in judgements if not j.parse_error and j.score is not None]
    if not usable:
        raise ValueError("no usable judgements after excluding parse errors")

    # Deterministic tie-break
    for j in usable:
        if j.judge_role == "deterministic":
            return float(j.score), j.score_kind

    # Otherwise weighted mean
    num = sum(j.score * weights.get(j.judge_role, 0.0) for j in usable)
    den = sum(weights.get(j.judge_role, 0.0) for j in usable)
    if den == 0:
        raise ValueError(f"no positive weights for any judge_role in {[j.judge_role for j in usable]}")
    return num / den, "rubric_aggregate"
```

- [ ] **Step 8: Run all judge tests to verify they pass**

Run: `uv run pytest tests/shared/eval/test_deterministic.py tests/shared/eval/test_aggregate.py -v`
Expected: 8 passed.

- [ ] **Step 9: Write the v0.1 judge_config bundle**

`shared/eval/judges/configs/v0.1.yaml`:

```yaml
# Sprint 1 judge bundle: deterministic-only. Specialist + generalist arrive in S3.
# Calibration map is empty by design — deterministic is always trusted; no κ needed.

version: v0.1
routing:
  by_expected_type:
    exact:  [deterministic]
    set:    [deterministic]
    rubric: [specialist]      # routing is defined but unused while no rubric examples exist
  by_lane_override: {}
judges:
  deterministic:
    config:
      string_normalize: [lowercase, strip_punct, whitespace_collapse]
      numeric_tolerance_abs: 1.0e-6
      numeric_tolerance_rel: 1.0e-3
  specialist:
    model_id: TBD              # registered in S3 plan
    rubric_set: rubrics_v0.1
  generalist:
    model_id: TBD
    protocol: g_eval_v1
aggregation:
  rule: weighted_mean
  tie_break: deterministic
  weights:
    deterministic: 1.0
    specialist: 0.7
    generalist: 0.3
calibration:
  human_calibration_set: null   # not built yet
  kappa_threshold: 0.80
  per_task_kappa: {}
trust:
  enforcement: lenient          # strict from S3 onward
rubrics: {}                     # populated when the first rubric lane lands in S3
notes: |
  Sprint 1 bootstrap bundle. Deterministic-only routing; no rubrics; lenient trust.
  Promotes to strict + populated calibration in the Sprint 3 plan.
```

`TBD` here is *not* a plan placeholder — it's a deliberately incomplete bundle marker. The bundle is only used in deterministic-only routing during Sprint 1; specialist/generalist `model_id`s get filled when Phase 3 work begins. Documented in `notes`.

- [ ] **Step 10: Write a tiny `register_bundle` helper and register v0.1**

Add to `shared/eval/judges/__init__.py`:

```python
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
```

Then run:
```bash
uv run python -c "from shared.eval.judges import register_bundle; register_bundle('v0.1'); print('ok')"
```
Expected: `ok`.

- [ ] **Step 11: Commit**

```bash
git add shared/eval/judges/ tests/shared/eval/test_deterministic.py tests/shared/eval/test_aggregate.py
git commit -m "Add shared/eval/judges/: deterministic scorer + aggregation + v0.1 bundle

Per spec §4: deterministic for exact/set; weighted-mean with deterministic
tie-break for aggregation. v0.1 bundle is deterministic-only, lenient trust;
specialist + generalist + calibration arrive in the Sprint 3 plan.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `shared/eval/runner/` — preflight + linear loop + budget + finalize

**Files:**
- Create: `shared/eval/runner/__init__.py`
- Create: `shared/eval/runner/teardown.py`
- Create: `shared/eval/runner/preflight.py`
- Create: `shared/eval/runner/runner.py`
- Create: `shared/eval/runner/cli.py`
- Create: `tests/shared/eval/test_preflight.py`
- Create: `tests/shared/eval/test_runner.py`

- [ ] **Step 1: Write the teardown hook interface**

`shared/eval/runner/teardown.py`:

```python
"""Teardown hook abstract base + LocalTeardownHook (no-op for Mac always-on).

Cloud-burst targets in S2+ subclass this and implement actual teardown.
"""
from __future__ import annotations

from typing import Protocol


class TeardownHook(Protocol):
    def teardown(self, reason: str) -> dict:
        """Teardown any on-demand compute. Return a receipt dict (may be empty)."""
        ...


class LocalTeardownHook:
    """No-op teardown for always-on targets (Mac, Spark)."""

    def teardown(self, reason: str) -> dict:
        return {"target": "local", "action": "noop", "reason": reason}
```

- [ ] **Step 2: Write the failing preflight test**

`tests/shared/eval/test_preflight.py`:

```python
"""Tests for the 6-step preflight."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.eval.runner.preflight import PreflightFailure, preflight_or_raise


@dataclass(frozen=True)
class FakeManifest:
    target_host: str = "mac"
    endpoint: str = "http://localhost:11434/v1"


def test_passes_when_all_steps_ok() -> None:
    # Each fake returns "ok" → no exception
    preflight_or_raise(
        check_postgres=lambda: None,
        check_manifest=lambda: FakeManifest(),
        check_trust_gate=lambda: None,
        check_rate_card=lambda h: None,
        check_endpoint_ready=lambda url, timeout_s: None,
    )


def test_fails_at_postgres_step() -> None:
    def boom():
        raise RuntimeError("connection refused")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=boom,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=lambda: None,
            check_rate_card=lambda h: None,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "postgres"


def test_fails_at_rate_card_step() -> None:
    def no_card(host):
        raise FileNotFoundError(f"no rate card for {host}")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=lambda: None,
            check_rate_card=no_card,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "rate_card"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/shared/eval/test_preflight.py -v`
Expected: `ModuleNotFoundError: No module named 'shared.eval.runner'`.

- [ ] **Step 4: Implement preflight**

`shared/eval/runner/__init__.py`:

```python
"""Eval runner: preflight, campaign loop, teardown hook."""

from shared.eval.runner.runner import run_campaign, RunResult
from shared.eval.runner.preflight import preflight_or_raise, PreflightFailure
from shared.eval.runner.teardown import TeardownHook, LocalTeardownHook

__all__ = [
    "run_campaign",
    "RunResult",
    "preflight_or_raise",
    "PreflightFailure",
    "TeardownHook",
    "LocalTeardownHook",
]
```

`shared/eval/runner/preflight.py`:

```python
"""6-step preflight per spec §5."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class PreflightFailure(RuntimeError):
    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"preflight failed at step={step!r}: {cause}")
        self.step = step
        self.cause = cause


@dataclass(frozen=True)
class PreflightHooks:
    check_postgres: Callable[[], None]
    check_manifest: Callable[[], Any]      # returns the resolved manifest
    check_trust_gate: Callable[[], None]
    check_rate_card: Callable[[str], None] # given target_host
    check_endpoint_ready: Callable[[str, float], None]  # url, timeout_s


def preflight_or_raise(
    check_postgres: Callable[[], None],
    check_manifest: Callable[[], Any],
    check_trust_gate: Callable[[], None],
    check_rate_card: Callable[[str], None],
    check_endpoint_ready: Callable[[str, float], None],
    endpoint_timeout_s: float = 60.0,
) -> Any:
    """Run all six steps in order; on failure raise PreflightFailure with step+cause.

    Returns the resolved manifest on success.
    """
    try:
        check_postgres()
    except Exception as e:
        raise PreflightFailure("postgres", e) from e

    try:
        manifest = check_manifest()
    except Exception as e:
        raise PreflightFailure("manifest", e) from e

    try:
        check_trust_gate()
    except Exception as e:
        raise PreflightFailure("trust_gate", e) from e

    try:
        check_rate_card(manifest.target_host)
    except Exception as e:
        raise PreflightFailure("rate_card", e) from e

    try:
        check_endpoint_ready(manifest.endpoint, endpoint_timeout_s)
    except Exception as e:
        raise PreflightFailure("endpoint_ready", e) from e

    return manifest
```

- [ ] **Step 5: Run the preflight test to verify it passes**

Run: `uv run pytest tests/shared/eval/test_preflight.py -v`
Expected: 3 passed.

- [ ] **Step 6: Write the failing runner test**

`tests/shared/eval/test_runner.py`:

```python
"""Tests for the campaign runner — happy path, budget halt, privacy guardrail."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from shared.db.connection import connect
from shared.db.migrations import apply_all
from shared.eval.judges import register_bundle
from shared.eval.runner import run_campaign
from shared.goldsets.loader import load_jsonl_to_postgres
from shared.models.manifest import load_manifest_yaml
from shared.models.registry import sync_to_postgres


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    apply_all(test=True)


def _bootstrap_fixtures(tmp_path: Path) -> None:
    """Set up: judge_config v0.1, qwen0.5b manifest, smoke seed."""
    _reset_test_db()
    register_bundle("v0.1", test=True)

    manifest_yaml = tmp_path / "m.yaml"
    manifest_yaml.write_text(
        'id: "qwen2.5:0.5b-instruct"\n'
        'family: qwen2.5\nsize: 0.5b\nrevision: "2024-09-19"\n'
        'runtime: ollama\nruntime_version: "0.3.12"\n'
        'target_host: mac\nendpoint: "http://localhost:11434/v1"\n'
        'capabilities: [chat]\ncontext_window: 32768\n'
        'default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 8}\n'
    )
    sync_to_postgres([load_manifest_yaml(manifest_yaml)], test=True)

    seed = tmp_path / "seed.jsonl"
    with seed.open("w") as f:
        f.write(json.dumps({
            "example_id": "ex_general_seed0001", "lane": "general",
            "source": "x", "annotator": "j", "annotated_at": "2026-05-26",
            "prompt_template": "general/multi-choice.j2",
            "inputs": {"question": "2+2?", "choices": {"A": "3", "B": "4", "C": "5", "D": "22"}},
            "expected": {"type": "exact", "value": "B"},
            "provenance_tag": "public", "never_to_third_party": False,
            "tags": [], "contamination_risk": "none",
        }) + "\n")
    load_jsonl_to_postgres(seed, version="smoke-v0.0", git_commit_sha="t", test=True)


def _stub_inference_response(content: str):
    """Patch InferenceClient.chat to return a canned ChatResponse."""
    from shared.inference.client import ChatResponse, Usage
    return ChatResponse(
        content=content,
        usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
        raw={"choices": [{"message": {"content": content}}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}},
    )


def test_happy_path_completes(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text(
        "Q: {{ question }}\nA. {{ choices.A }}\nB. {{ choices.B }}\nC. {{ choices.C }}\nD. {{ choices.D }}\nAnswer:"
    )

    with patch("shared.inference.client.InferenceClient.chat",
               return_value=_stub_inference_response("B")):
        rr = run_campaign(
            model_id="qwen2.5:0.5b-instruct",
            gold_set_version="smoke-v0.0",
            judge_config_version="v0.1",
            max_cost_usd=1.00,
            template_root=template_root,
            test=True,
        )

    assert rr.status == "completed"
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT score, score_kind FROM result WHERE run_id = %s", (rr.run_id,))
        rows = cur.fetchall()
    assert rows == [(1.0, "binary")]


def test_budget_halt(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text("Q: {{ question }} A.")

    # max_cost_usd=0 → first non-zero cost increment trips the halt.
    # The mac-mini rate card has wall_usd_per_hour=0.05, so even a 1ms wall = nonzero.
    with patch("shared.inference.client.InferenceClient.chat",
               return_value=_stub_inference_response("B")):
        rr = run_campaign(
            model_id="qwen2.5:0.5b-instruct",
            gold_set_version="smoke-v0.0",
            judge_config_version="v0.1",
            max_cost_usd=0.0,
            template_root=template_root,
            test=True,
        )

    assert rr.status == "halted_budget"
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `uv run pytest tests/shared/eval/test_runner.py -v`
Expected: `ImportError: cannot import name 'run_campaign'`.

- [ ] **Step 8: Implement the runner**

`shared/eval/runner/runner.py`:

```python
"""Campaign runner: preflight → per-example dispatch → judges → finalize.

One linear pass through the gold-set examples. Per spec §1 + §5.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.db.connection import connect
from shared.eval.cost.accountant import CostAccountant, load_rate_card
from shared.eval.judges import (
    DeterministicConfig,
    Judgement,
    aggregate,
    deterministic_score,
)
from shared.eval.runner.preflight import PreflightFailure, preflight_or_raise
from shared.eval.runner.teardown import LocalTeardownHook, TeardownHook
from shared.goldsets.render import render_prompt
from shared.goldsets.schema import Expected
from shared.inference.client import ChatRequest, InferenceClient, Message
from shared.inference.errors import ErrorClass, InferenceError
from shared.models.manifest import ModelManifest
from shared.models.registry import resolve


@dataclass(frozen=True)
class RunResult:
    run_id: uuid.UUID
    status: str
    cost_actual_usd: float
    n_examples_scored: int
    n_examples_errored: int


def run_campaign(
    model_id: str,
    gold_set_version: str,
    judge_config_version: str,
    max_cost_usd: float,
    template_root: Path,
    experiment_id: str | None = None,
    test: bool = False,
    teardown_hook: TeardownHook | None = None,
    inference_client_factory=None,  # for test injection
) -> RunResult:
    teardown_hook = teardown_hook or LocalTeardownHook()
    run_id = uuid.uuid4()
    started_at = time.time()

    # --- Preflight (steps 1–5; step 6 = write `run` row, just below) ---
    try:
        manifest = preflight_or_raise(
            check_postgres=lambda: _check_postgres(test=test),
            check_manifest=lambda: resolve(model_id, test=test),
            check_trust_gate=lambda: _check_trust_gate(judge_config_version, gold_set_version, test=test),
            check_rate_card=lambda host: load_rate_card(host),
            check_endpoint_ready=lambda url, t: None,   # Ollama exposes /v1 immediately; skip in v0.1
        )
    except PreflightFailure as f:
        # postgres step failed → we can't write a run row; bubble up
        if f.step == "postgres":
            raise
        # otherwise write a halted_setup row and return
        _write_run_row(
            run_id=run_id, model_id=model_id, model_manifest={},
            gold_set_version=gold_set_version,
            judge_config_version=judge_config_version, judge_config={},
            max_cost_usd=max_cost_usd, n_examples_total=0,
            status="halted_setup",
            error={"step": f.step, "cause": str(f.cause)},
            experiment_id=experiment_id, test=test,
        )
        teardown_hook.teardown(f"halted_setup at {f.step}")
        return RunResult(run_id=run_id, status="halted_setup",
                         cost_actual_usd=0.0, n_examples_scored=0, n_examples_errored=0)

    # --- Load fixtures ---
    examples = _fetch_examples(gold_set_version, test=test)
    bundle = _fetch_bundle(judge_config_version, test=test)
    cost_accountant = CostAccountant.for_target(manifest.target_host)

    # --- Privacy guardrail (spec §5) ---
    # Mac is sovereign Tier 1 → no examples can violate. Check exists for future-proofing.
    try:
        _enforce_privacy_guardrail(manifest, examples)
    except PreflightFailure as f:
        _write_run_row(
            run_id=run_id, model_id=model_id, model_manifest=manifest.model_dump(),
            gold_set_version=gold_set_version,
            judge_config_version=judge_config_version, judge_config=bundle,
            max_cost_usd=max_cost_usd, n_examples_total=len(examples),
            status="halted_setup",
            error={"step": f.step, "cause": str(f.cause)},
            experiment_id=experiment_id, test=test,
        )
        teardown_hook.teardown(f"halted_setup at {f.step}")
        return RunResult(run_id=run_id, status="halted_setup",
                         cost_actual_usd=0.0, n_examples_scored=0, n_examples_errored=0)

    # --- Write initial run row (step 6) ---
    _write_run_row(
        run_id=run_id, model_id=model_id,
        model_manifest=manifest.model_dump(),
        gold_set_version=gold_set_version,
        judge_config_version=judge_config_version,
        judge_config=bundle,
        max_cost_usd=max_cost_usd,
        n_examples_total=len(examples),
        status="running",
        experiment_id=experiment_id,
        test=test,
    )

    # --- Build client ---
    client = (inference_client_factory or _default_client_factory)(manifest)

    # --- Linear loop ---
    cost_accumulated = 0.0
    n_scored = 0
    n_errored = 0
    status = "completed"
    halt_error: dict | None = None

    for ex in examples:
        # Render
        rendered = render_prompt(template_root, ex["prompt_template"], ex["inputs"])

        # Inference
        call_started = time.time()
        result_id = uuid.uuid4()
        try:
            req = ChatRequest(
                messages=[Message(role="user", content=rendered)],
                temperature=manifest.default_sampling.temperature,
                top_p=manifest.default_sampling.top_p,
                max_tokens=manifest.default_sampling.max_tokens,
            )
            resp = client.chat(req)
            response_text = resp.content
            prompt_tokens = resp.usage.prompt_tokens
            completion_tokens = resp.usage.completion_tokens
            error_class = None
            error_body = None
        except InferenceError as e:
            response_text = None
            prompt_tokens = None
            completion_tokens = None
            if e.error_class is ErrorClass.CATASTROPHIC:
                status = "halted_endpoint_error"
                halt_error = {"cause": str(e), "error_class": e.error_class.value}
            error_class = "client_fatal" if e.error_class is ErrorClass.CLIENT_FATAL else (
                "retryable_exhausted" if e.error_class is ErrorClass.RETRYABLE else "catastrophic"
            )
            error_body = {"message": str(e), "body": e.body}
        wall_ms = int((time.time() - call_started) * 1000)

        # Cost
        cost_inc = cost_accountant.cost_per_call(prompt_tokens, completion_tokens, wall_ms)
        cost_accumulated += cost_inc

        # Score (deterministic only in v0.1)
        agg_score: float | None = None
        agg_kind: str | None = None
        judgement_row: Judgement | None = None
        if response_text is not None:
            expected = Expected(**ex["expected"])
            cfg = DeterministicConfig(**bundle["judges"]["deterministic"]["config"])
            try:
                if expected.type in {"exact", "set"}:
                    raw_score = deterministic_score(response_text, expected, cfg)
                    judgement_row = Judgement(
                        judge_role="deterministic",
                        score=raw_score,
                        score_kind="binary" if expected.type == "exact" else "scalar",
                    )
                    agg_score, agg_kind = aggregate(
                        [judgement_row], bundle["aggregation"]["weights"]
                    )
                else:
                    # No specialist in v0.1 → mark as parse-failed-style error on the result
                    error_class = "judge_parse_failed"
                    error_body = {"reason": "rubric routing not implemented in Sprint 1"}
            except Exception as e:
                error_class = "judge_parse_failed"
                error_body = {"reason": str(e)}

        # Persist `result`
        _write_result_row(
            id=result_id, run_id=run_id, example=ex,
            gold_set_version=gold_set_version,
            rendered=rendered, response=response_text,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            cost_inc=cost_inc, wall_ms=wall_ms,
            score=agg_score, score_kind=agg_kind,
            error_class=error_class, error_body=error_body,
            nondeterministic_runtime="seed" not in manifest.capabilities,
            test=test,
        )

        # Persist `judgement`
        if judgement_row is not None:
            _write_judgement_row(
                result_id=result_id, judgement=judgement_row, bundle=bundle, test=test,
            )

        if error_class is None:
            n_scored += 1
        else:
            n_errored += 1

        if status == "halted_endpoint_error":
            break

        # Budget check
        if cost_accumulated > max_cost_usd:
            status = "halted_budget"
            halt_error = {"cause": "max_cost_usd exceeded",
                          "cost_accumulated": cost_accumulated, "max": max_cost_usd}
            break

    # --- Teardown + finalize ---
    teardown_receipt = teardown_hook.teardown(f"run_finalize_{status}")
    finished_at = time.time()
    _finalize_run_row(
        run_id=run_id, status=status, finished_at=finished_at,
        wall_seconds=int(finished_at - started_at),
        cost_actual_usd=cost_accumulated,
        n_examples_scored=n_scored, n_examples_errored=n_errored,
        summary_scores=_compute_summary(run_id, test=test),
        error=halt_error,
        notes=f"teardown_receipt={json.dumps(teardown_receipt)}",
        test=test,
    )

    return RunResult(
        run_id=run_id, status=status,
        cost_actual_usd=cost_accumulated,
        n_examples_scored=n_scored, n_examples_errored=n_errored,
    )


# ----- helpers -----

def _check_postgres(test: bool) -> None:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        if cur.fetchone() != (1,):
            raise RuntimeError("postgres healthcheck returned non-1")


def _check_trust_gate(judge_config_version: str, gold_set_version: str, test: bool) -> None:
    """Stub for v0.1: deterministic-only routing is always trusted."""
    bundle = _fetch_bundle(judge_config_version, test=test)
    if bundle["trust"]["enforcement"] == "lenient":
        return
    # Strict mode would enforce per-task kappas here; Sprint 1 bundle is lenient.
    raise NotImplementedError("strict trust gate arrives in Sprint 3 plan")


def _enforce_privacy_guardrail(manifest: ModelManifest, examples: list[dict]) -> None:
    tier1_hosts = {"mac", "spark", "cloud-burst-a3", "cloud-burst-p5"}
    if manifest.target_host in tier1_hosts:
        return
    for ex in examples:
        if ex.get("never_to_third_party"):
            raise PreflightFailure(
                "privacy_violation",
                RuntimeError(f"example {ex['example_id']} cannot reach non-Tier-1 host "
                             f"{manifest.target_host}"),
            )


def _fetch_examples(gold_set_version: str, test: bool) -> list[dict[str, Any]]:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT example_id::text, lane, prompt_template, inputs, expected, "
            "       never_to_third_party "
            "FROM gold_example WHERE version = %s ORDER BY example_id",
            (gold_set_version,),
        )
        rows = cur.fetchall()
    return [
        {"example_id": r[0], "lane": r[1], "prompt_template": r[2],
         "inputs": r[3], "expected": r[4], "never_to_third_party": r[5]}
        for r in rows
    ]


def _fetch_bundle(version: str, test: bool) -> dict:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute("SELECT bundle FROM judge_config WHERE version = %s", (version,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"no judge_config with version={version!r}")
    return row[0]


def _default_client_factory(manifest: ModelManifest) -> InferenceClient:
    return InferenceClient(endpoint=manifest.endpoint, model=manifest.id, timeout_s=60.0)


def _write_run_row(
    *, run_id, model_id, model_manifest, gold_set_version, judge_config_version,
    judge_config, max_cost_usd, n_examples_total, status,
    error=None, experiment_id=None, test=False,
):
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO run (
                id, model_id, model_manifest, gold_set_version,
                judge_config_version, judge_config,
                max_cost_usd, n_examples_total, status, error, experiment_id
            ) VALUES (
                %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s
            )
            """,
            (run_id, model_id, json.dumps(model_manifest), gold_set_version,
             judge_config_version, json.dumps(judge_config),
             max_cost_usd, n_examples_total, status,
             json.dumps(error) if error is not None else None, experiment_id),
        )


def _write_result_row(
    *, id, run_id, example, gold_set_version, rendered, response,
    prompt_tokens, completion_tokens,
    cost_inc, wall_ms, score, score_kind, error_class, error_body,
    nondeterministic_runtime, test=False,
):
    usage = (
        {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        if prompt_tokens is not None else None
    )
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO result (
                id, run_id, example_id, gold_set_version, rendered_prompt,
                response, usage, cost_increment_usd, wall_ms,
                score, score_kind, error_class, error_body,
                nondeterministic_runtime, started_at, finished_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s::jsonb, %s, %s,
                %s, %s, %s, %s::jsonb,
                %s, now(), now()
            )
            """,
            (
                id, run_id, example["example_id"], gold_set_version, rendered,
                response, json.dumps(usage) if usage else None, cost_inc, wall_ms,
                score, score_kind, error_class,
                json.dumps(error_body) if error_body else None,
                nondeterministic_runtime,
            ),
        )


def _write_judgement_row(*, result_id, judgement: Judgement, bundle, test=False):
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO judgement (
                id, result_id, judge_role, judge_manifest,
                score, score_kind, parse_error
            ) VALUES (
                %s, %s, %s, %s::jsonb, %s, %s, %s
            )
            """,
            (
                uuid.uuid4(), result_id, judgement.judge_role,
                json.dumps(bundle["judges"].get(judgement.judge_role, {})),
                judgement.score, judgement.score_kind, judgement.parse_error,
            ),
        )


def _compute_summary(run_id, test=False) -> dict:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT avg(score) FROM result "
            "WHERE run_id = %s AND score IS NOT NULL",
            (run_id,),
        )
        avg = cur.fetchone()[0]
    return {"avg_score": float(avg) if avg is not None else None}


def _finalize_run_row(
    *, run_id, status, finished_at, wall_seconds, cost_actual_usd,
    n_examples_scored, n_examples_errored, summary_scores, error, notes, test=False,
):
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE run SET
                finished_at = to_timestamp(%s),
                wall_seconds = %s,
                cost_actual_usd = %s,
                n_examples_scored = %s,
                n_examples_errored = %s,
                summary_scores = %s::jsonb,
                status = %s,
                error = %s::jsonb,
                notes = %s
            WHERE id = %s
            """,
            (
                finished_at, wall_seconds, cost_actual_usd,
                n_examples_scored, n_examples_errored,
                json.dumps(summary_scores), status,
                json.dumps(error) if error is not None else None,
                notes, run_id,
            ),
        )
```

- [ ] **Step 9: Implement the CLI**

`shared/eval/runner/cli.py`:

```python
"""CLI for the eval runner.

Examples:
    uv run python -m shared.eval.runner.cli \\
        --model qwen2.5:0.5b-instruct \\
        --gold-set smoke-v0.0 \\
        --judge-config v0.1 \\
        --max-cost-usd 1.00 \\
        --template-root experiments/0001-inference-contract-validation/prompt_templates \\
        --experiment 0001-inference-contract-validation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.eval.runner.runner import run_campaign


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--gold-set", required=True, dest="gold_set_version")
    p.add_argument("--judge-config", required=True, dest="judge_config_version")
    p.add_argument("--max-cost-usd", type=float, required=True)
    p.add_argument("--template-root", required=True, type=Path)
    p.add_argument("--experiment", default=None, dest="experiment_id")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()

    rr = run_campaign(
        model_id=args.model,
        gold_set_version=args.gold_set_version,
        judge_config_version=args.judge_config_version,
        max_cost_usd=args.max_cost_usd,
        template_root=args.template_root,
        experiment_id=args.experiment_id,
        test=args.test,
    )
    print(f"run_id={rr.run_id} status={rr.status} "
          f"cost=${rr.cost_actual_usd:.6f} "
          f"scored={rr.n_examples_scored} errored={rr.n_examples_errored}")
    sys.exit(0 if rr.status == "completed" else 1)


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 10: Run runner tests to verify they pass**

Run: `uv run pytest tests/shared/eval/test_runner.py -v`
Expected: 2 passed.

- [ ] **Step 11: Commit**

```bash
git add shared/eval/runner/ tests/shared/eval/test_preflight.py tests/shared/eval/test_runner.py
git commit -m "Add shared/eval/runner/: preflight, campaign loop, teardown hook, CLI

Per spec §5: 6-step preflight; linear example loop; per-result budget check;
LocalTeardownHook for always-on targets; CLI entry point.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: experiment `0001-inference-contract-validation/` — end-to-end smoke

**Files:**
- Create: `experiments/0001-inference-contract-validation/README.md`
- Create: `experiments/0001-inference-contract-validation/run.sh`

- [ ] **Step 1: Write the experiment README (Hypothesis/Setup/Method first per repo convention)**

`experiments/0001-inference-contract-validation/README.md`:

```markdown
# 0001-inference-contract-validation

**Area:** `inference` · **Status:** running · **Started:** 2026-05-26

## Hypothesis

The eval substrate (inference contract + run-storage + gold-set loader + deterministic
judge + runner) wires together end-to-end on the Mac mini against a small local model,
producing a completed `run` row with three `result` rows, each scored by the deterministic
judge, with measurable cost.

If it doesn't, one of the four hard-to-reverse decisions has a flaw and the spec needs
revision.

## Setup

- Hardware: M4 Mac mini (16 GB unified memory)
- Postgres 16 + pgvector (extension installed, unused)
- Ollama 0.3.x serving `qwen2.5:0.5b-instruct` at `http://localhost:11434/v1`
- Gold set: 3-example smoke seed (`seed.jsonl`) loaded as `smoke-v0.0`
- Judge config: `v0.1` (deterministic-only, lenient trust)
- Rate card: `mac-mini.yaml` ($0.05/wall-hour)

Run `uv run python scripts/hardware_report.py` and paste the output here when first
running this experiment:

    <paste hardware report>

## Method

1. Pull the model: `ollama pull qwen2.5:0.5b-instruct`
2. Apply migrations: `uv run python -m shared.db.migrations apply`
3. Sync manifests: `uv run python -c "from shared.models.registry import sync_all; sync_all()"`
4. Register judge bundle: `uv run python -c "from shared.eval.judges import register_bundle; register_bundle('v0.1')"`
5. Load the seed:
   ```bash
   uv run python -c "
   from pathlib import Path
   from shared.goldsets.loader import load_jsonl_to_postgres
   load_jsonl_to_postgres(
       Path('experiments/0001-inference-contract-validation/seed.jsonl'),
       version='smoke-v0.0', git_commit_sha='wip-smoke')
   "
   ```
6. Run the campaign via `./run.sh`.

## Results

(populate after first run; commit each result observation)

- `run_id`: TBD on first run
- `status`: expected `completed`
- `cost_actual_usd`: expected ~$0.0000xx (wall-time only on mac-mini rate card)
- Per-example scores: expected `1.0` for the arithmetic and ordering questions (the
  0.5B model may miss the geography one — that's fine; this is a substrate smoke,
  not a model evaluation).

## Conclusion

(populate after first run)

- Hypothesis supported / not supported.
- Next experiment: scale up to a larger Mac model (`qwen2.5:7b-instruct`) when the
  Spark arrives; in the meantime, draft the Phase-1 writeup.
```

- [ ] **Step 2: Write the convenience launcher**

`experiments/0001-inference-contract-validation/run.sh`:

```bash
#!/usr/bin/env bash
# Convenience launcher for the 0001 smoke run.
# Assumes Ollama is up at http://localhost:11434 and qwen2.5:0.5b-instruct is pulled.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

uv run python -m shared.eval.runner.cli \
    --model "qwen2.5:0.5b-instruct" \
    --gold-set "smoke-v0.0" \
    --judge-config "v0.1" \
    --max-cost-usd 1.00 \
    --template-root experiments/0001-inference-contract-validation/prompt_templates \
    --experiment "0001-inference-contract-validation"
```

Make executable:
```bash
chmod +x experiments/0001-inference-contract-validation/run.sh
```

- [ ] **Step 3: Execute the smoke run**

Run: `experiments/0001-inference-contract-validation/run.sh`
Expected: prints a line like `run_id=<uuid> status=completed cost=$0.000005 scored=3 errored=0` (or `scored=2 errored=1` if the 0.5B model misses one). Exits 0.

If it errors:
- Check Ollama is up: `curl http://localhost:11434/v1/models`
- Check Postgres has the manifest: `psql -d ai_experiments -c "SELECT id FROM model_manifest;"`
- Check the bundle was registered: `psql -d ai_experiments -c "SELECT version FROM judge_config;"`
- Check the seed loaded: `psql -d ai_experiments -c "SELECT version, count(*) FROM gold_example GROUP BY version;"`

- [ ] **Step 4: Capture results in the README**

Update the `## Results` section with the actual `run_id`, `status`, `cost_actual_usd`, and per-example scores from:

```bash
psql -d ai_experiments -c "
SELECT id, status, cost_actual_usd, n_examples_scored, n_examples_errored
FROM run ORDER BY started_at DESC LIMIT 1;
"
psql -d ai_experiments -c "
SELECT example_id, score, score_kind, response
FROM result WHERE run_id = (SELECT id FROM run ORDER BY started_at DESC LIMIT 1);
"
```

Paste the output into the README's Results section.

- [ ] **Step 5: Commit**

```bash
git add experiments/0001-inference-contract-validation/README.md experiments/0001-inference-contract-validation/run.sh
git commit -m "Add experiment 0001-inference-contract-validation: end-to-end smoke

First end-to-end exercise of the eval substrate. Status will be updated in the
README's Results section after the run.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Update `EXPERIMENTS.md` and `ROADMAP.md` statuses

**Files:**
- Modify: `EXPERIMENTS.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1: Update `EXPERIMENTS.md`**

Replace the placeholder row with:

```markdown
| ID | Area | Title | Status | Started | Result (one line) |
|------|------------|------------------------------|----------|------------|-------------------|
| 0001 | inference  | inference-contract-validation | running  | 2026-05-26 | end-to-end smoke of the substrate on Mac mini |
```

- [ ] **Step 2: Update `ROADMAP.md` Phase 1 status**

Find the line:

```markdown
## Phase 1 — Sovereign inference substrate

**Status:** planned.
```

Change to:

```markdown
## Phase 1 — Sovereign inference substrate

**Status:** in progress (started 2026-05-26).
```

- [ ] **Step 3: Commit**

```bash
git add EXPERIMENTS.md ROADMAP.md
git commit -m "Mark Phase 1 in progress; register experiment 0001 in EXPERIMENTS.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Full test sweep + ruff

**Files:**
- (no new files — verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass — migrations (2) + errors (10: 8 parametrize + 2 standalone) + client (3) + manifest (2) + registry (2) + cost (3) + goldset schema (3) + render (2) + loader (3) + deterministic (4) + aggregate (4) + preflight (3) + runner (2) = **43 passed**.

If anything fails, fix it inline and re-run.

- [ ] **Step 2: Run ruff**

Run: `uv run ruff check .`
Expected: 0 errors. Fix any inline (most likely: unused imports, line length > 100).

- [ ] **Step 3: Commit any ruff fixes**

```bash
git add -u
git commit -m "Ruff cleanup after Sprint 1 substrate landed

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>" || echo "nothing to commit"
```

---

## Sprint 1 done state (acceptance check)

After all tasks complete, verify:

- [ ] `git log --oneline | head -15` shows ~12 atomic commits from this plan.
- [ ] `uv run pytest -v` → 41 passed.
- [ ] `psql -d ai_experiments -c "SELECT id, status FROM run ORDER BY started_at DESC LIMIT 5;"` shows at least one `completed` run.
- [ ] `experiments/0001-inference-contract-validation/README.md` has its Results section populated.
- [ ] `ROADMAP.md` Phase 1 status is `in progress`.
- [ ] `EXPERIMENTS.md` lists experiment 0001.

The substrate is now usable. Follow-up plans:
- **Sprint 2 plan** (after Spark arrives ~Jun 15): add Spark target, vLLM-on-Spark or NIM bring-up, cloud-burst target, second model manifest.
- **Sprint 3 plan**: real specialist + generalist judges, human-calibration set, κ measurement, strict trust gate, bias stress tests.
- **Sprint 4 plan**: lane depth across SEA/Japanese/OCR/finance, additional rubrics.
