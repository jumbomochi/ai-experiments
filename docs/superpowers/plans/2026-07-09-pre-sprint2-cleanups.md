# Pre-Sprint-2 Cleanups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four targeted cleanups (uuid5→text PK migration, guardrail relocation, double bundle-fetch fix, tests/integration/ reorganization) that leave the codebase in a coherent state before Sprint 2 begins substantive work.

**Architecture:** Each cleanup is an independent change applied in order: schema migration (C1) → pure code refactor (C2) → signature change across preflight+runner+tests (C3) → file move (C4). C2 and C3 both touch runner.py; C1 must complete before the dev DB reload.

**Tech Stack:** Python 3.11+, psycopg2, pytest, uv, Postgres.

## Global Constraints

- All Python: `from __future__ import annotations` at the top of every new file.
- No new dependencies — use only what's already in the project.
- TDD: write the failing test before the implementation for every code change.
- Run `uv run pytest tests/shared/ -v` (unit tests only, no integration) to verify after each task. Task 4 switches the integration test location; run `uv run pytest tests/ -v` there.
- Do not run `tests/shared/eval/test_runner.py` (integration — requires live Postgres) as part of the automated test gate unless you have a running test DB.
- `example_id::text` cast in `_fetch_examples` refers to `shared/eval/runner/runner.py:304`.
- The migration applier CLI: `uv run python -m shared.db.migrations apply [--test]`.

---

### Task 1: C1 — Migration 002 + loader/runner cleanup

Converts `gold_example.example_id` and `result.example_id` from `uuid` to `text`, removes the `_example_uuid()` helper from the loader, and removes the now-redundant `::text` cast from the runner query.

**Files:**
- Create: `migrations/002_gold_example_readable_id.sql`
- Modify: `shared/goldsets/loader.py`
- Modify: `shared/eval/runner/runner.py` (only `_fetch_examples`, lines 301–313)
- Modify: `tests/shared/goldsets/test_loader.py` (add one test)

**Interfaces:**
- Produces: `load_jsonl_to_postgres` now inserts `ex.example_id` (a `str` like `"ex_general_seed0001"`) directly into the `gold_example.example_id` text column, unchanged.

- [ ] **Step 1: Write the migration SQL**

```sql
-- migrations/002_gold_example_readable_id.sql
-- Dev DB only: truncate all data in FK order, then convert uuid PKs to text.
-- No BEGIN/COMMIT — the applier (shared/db/migrations.py) owns the transaction.

TRUNCATE TABLE judgement;
TRUNCATE TABLE result;
TRUNCATE TABLE run;
TRUNCATE TABLE gold_example;
TRUNCATE TABLE gold_set_version;

ALTER TABLE gold_example ALTER COLUMN example_id TYPE text;
ALTER TABLE result ALTER COLUMN example_id TYPE text;
```

- [ ] **Step 2: Write the failing test**

Add to `tests/shared/goldsets/test_loader.py` (after the existing `test_load_rejects_empty_jsonl` test):

```python
def test_load_stores_readable_example_id(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT example_id FROM gold_example")
        rows = [r[0] for r in cur.fetchall()]
    assert rows == ["ex_general_seed0001"]
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest tests/shared/goldsets/test_loader.py::test_load_stores_readable_example_id -v
```

Expected: FAIL — the loader currently calls `_example_uuid("ex_general_seed0001")` which inserts a UUID-derived string (e.g. `"c61a4d9a-..."`) not the readable ID.

- [ ] **Step 4: Fix the loader**

In `shared/goldsets/loader.py`:

Remove the `import uuid` line at line 13 and the `_example_uuid` function (lines 23–25):

```python
# DELETE these lines:
import uuid

def _example_uuid(example_id: str) -> uuid.UUID:
    """Map our ex_<lane>_<suffix> id to a deterministic uuid5 for the uuid PK."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"goldsets://{example_id}")
```

In `load_jsonl_to_postgres`, change the INSERT at line 97 from:

```python
version, _example_uuid(ex.example_id), ex.lane,
```

to:

```python
version, ex.example_id, ex.lane,
```

The full `for ex in examples:` INSERT block after the fix:

```python
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
                    version, ex.example_id, ex.lane,
                    ex.source, ex.annotator, ex.annotated_at,
                    ex.prompt_template,
                    json.dumps(ex.inputs),
                    json.dumps(ex.expected.model_dump()),
                    ex.provenance_tag,
                    ex.never_to_third_party,
                    ex.tags, ex.contamination_risk,
                ),
            )
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/shared/goldsets/test_loader.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Remove the redundant `::text` cast from the runner query**

In `shared/eval/runner/runner.py`, change `_fetch_examples` (lines 301–313) from:

```python
def _fetch_examples(gold_set_version: str, test: bool) -> list[dict[str, Any]]:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT example_id::text, lane, prompt_template, inputs, expected, "
            "       never_to_third_party "
            "FROM gold_example WHERE version = %s ORDER BY example_id",
            (gold_set_version,),
        )
```

to:

```python
def _fetch_examples(gold_set_version: str, test: bool) -> list[dict[str, Any]]:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT example_id, lane, prompt_template, inputs, expected, "
            "       never_to_third_party "
            "FROM gold_example WHERE version = %s ORDER BY example_id",
            (gold_set_version,),
        )
```

- [ ] **Step 7: Run all unit tests**

```bash
uv run pytest tests/shared/ -v --ignore=tests/shared/eval/test_runner.py
```

Expected: all unit tests PASS. (Ignore test_runner.py — it's an integration test requiring live Postgres.)

- [ ] **Step 8: Apply the migration to the dev DB**

```bash
uv run python -m shared.db.migrations apply
```

Expected output: `applied: 002`

Confirm:

```bash
uv run python -m shared.db.migrations list
```

Expected: both `001` and `002` show `✓`.

- [ ] **Step 9: Reload the dev DB (if there was previously loaded data)**

If you had gold set data in the dev DB before, reload it now. The JSONL for the smoke set lives at `experiments/0001-inference-contract-validation/seed.jsonl`. Run:

```bash
uv run python -c "
from shared.goldsets.loader import load_jsonl_to_postgres
from pathlib import Path
import subprocess
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
load_jsonl_to_postgres(
    Path('experiments/0001-inference-contract-validation/seed.jsonl'),
    version='smoke-v0.0',
    git_commit_sha=sha,
)
print('done')
"
```

If you get `done`, the dev DB now has readable PKs. If you see `0 rows`, the same (version, sha) was already present — safe to ignore.

- [ ] **Step 10: Commit**

```bash
git add migrations/002_gold_example_readable_id.sql \
        shared/goldsets/loader.py \
        shared/eval/runner/runner.py \
        tests/shared/goldsets/test_loader.py
git commit -m "feat: migrate gold_example.example_id uuid → text readable PK (C1)"
```

---

### Task 2: C2 — Move privacy guardrail to `shared/inference/guardrails.py`

Extracts `_enforce_privacy_guardrail` from `runner.py` into a proper module-level function in `shared/inference/`, making it importable and testable independently of the runner.

**Files:**
- Create: `tests/shared/inference/__init__.py`
- Create: `tests/shared/inference/test_guardrails.py`
- Create: `shared/inference/guardrails.py`
- Modify: `shared/inference/__init__.py`
- Modify: `shared/eval/runner/runner.py` (remove private def, add import + call)

**Interfaces:**
- Consumes: `shared.eval.runner.preflight.PreflightFailure`; `shared.models.manifest.ModelManifest`
- Produces: `enforce_privacy_guardrail(manifest: ModelManifest, examples: list[dict]) -> None` — raises `PreflightFailure("privacy_violation", ...)` when a `never_to_third_party=True` example would reach a non-Tier-1 host.

- [ ] **Step 1: Create the test package `__init__`**

```bash
touch tests/shared/inference/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/shared/inference/test_guardrails.py`:

```python
"""Unit tests for the inference-layer privacy guardrail."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.eval.runner.preflight import PreflightFailure
from shared.inference.guardrails import enforce_privacy_guardrail


@dataclass(frozen=True)
class FakeManifest:
    target_host: str


def test_tier1_host_allows_private_example() -> None:
    for host in ("mac", "spark", "cloud-burst-l4", "cloud-burst-a2",
                 "cloud-burst-a3", "cloud-burst-p5"):
        manifest = FakeManifest(target_host=host)
        examples = [{"example_id": "ex_1", "never_to_third_party": True}]
        enforce_privacy_guardrail(manifest, examples)  # must not raise


def test_non_tier1_host_with_private_example_raises() -> None:
    manifest = FakeManifest(target_host="openai-gpt4")
    examples = [{"example_id": "ex_secret", "never_to_third_party": True}]
    with pytest.raises(PreflightFailure) as ei:
        enforce_privacy_guardrail(manifest, examples)
    assert ei.value.step == "privacy_violation"
    assert "ex_secret" in str(ei.value)


def test_non_tier1_host_with_public_example_passes() -> None:
    manifest = FakeManifest(target_host="openai-gpt4")
    examples = [{"example_id": "ex_public", "never_to_third_party": False}]
    enforce_privacy_guardrail(manifest, examples)  # must not raise
```

- [ ] **Step 3: Run to verify they fail**

```bash
uv run pytest tests/shared/inference/test_guardrails.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'shared.inference.guardrails'`.

- [ ] **Step 4: Create `shared/inference/guardrails.py`**

```python
"""Privacy guardrail enforced at the inference boundary.

Tier 1 sovereign hosts (where we control the full runtime and data flow)
are exempt. All other hosts are blocked from receiving examples marked
never_to_third_party.
"""
from __future__ import annotations

from shared.eval.runner.preflight import PreflightFailure
from shared.models.manifest import ModelManifest

_TIER1_HOSTS = frozenset({
    "mac", "spark",
    "cloud-burst-l4", "cloud-burst-a2", "cloud-burst-a3", "cloud-burst-p5",
})


def enforce_privacy_guardrail(manifest: ModelManifest, examples: list[dict]) -> None:
    if manifest.target_host in _TIER1_HOSTS:
        return
    for ex in examples:
        if ex.get("never_to_third_party"):
            raise PreflightFailure(
                "privacy_violation",
                RuntimeError(
                    f"example {ex['example_id']} cannot reach non-Tier-1 host "
                    f"{manifest.target_host}"
                ),
            )
```

- [ ] **Step 5: Run to verify tests pass**

```bash
uv run pytest tests/shared/inference/test_guardrails.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Export from `shared/inference/__init__.py`**

Current `shared/inference/__init__.py`:

```python
"""OpenAI-compatible inference client and error handling."""

from shared.inference.client import (
    ChatRequest,
    ChatResponse,
    InferenceClient,
    Message,
    Usage,
)
from shared.inference.errors import ErrorClass, InferenceError

__all__ = [
    "InferenceClient",
    "ChatRequest",
    "Message",
    "ChatResponse",
    "Usage",
    "ErrorClass",
    "InferenceError",
]
```

Replace with:

```python
"""OpenAI-compatible inference client, error handling, and privacy guardrail."""

from shared.inference.client import (
    ChatRequest,
    ChatResponse,
    InferenceClient,
    Message,
    Usage,
)
from shared.inference.errors import ErrorClass, InferenceError
from shared.inference.guardrails import enforce_privacy_guardrail

__all__ = [
    "InferenceClient",
    "ChatRequest",
    "Message",
    "ChatResponse",
    "Usage",
    "ErrorClass",
    "InferenceError",
    "enforce_privacy_guardrail",
]
```

- [ ] **Step 7: Update `runner.py` — add import, replace call, remove private def**

At the top of `shared/eval/runner/runner.py`, add to the existing imports block:

```python
from shared.inference import enforce_privacy_guardrail
```

(Add it after the existing `from shared.inference.client import ...` line.)

In `run_campaign` (around line 94), change:

```python
        _enforce_privacy_guardrail(manifest, examples)
```

to:

```python
        enforce_privacy_guardrail(manifest, examples)
```

Delete the entire `_enforce_privacy_guardrail` function (lines 288–298 in the original file):

```python
# DELETE this function:
def _enforce_privacy_guardrail(manifest: ModelManifest, examples: list[dict]) -> None:
    tier1_hosts = {"mac", "spark", "cloud-burst-a3", "cloud-burst-p5", "cloud-burst-l4", "cloud-burst-a2"}
    if manifest.target_host in tier1_hosts:
        return
    for ex in examples:
        if ex.get("never_to_third_party"):
            raise PreflightFailure(
                "privacy_violation",
                RuntimeError(f"example {ex['example_id']} cannot reach non-Tier-1 host "
                             f"{manifest.target_host}"),
            )
```

- [ ] **Step 8: Run all unit tests**

```bash
uv run pytest tests/shared/ -v --ignore=tests/shared/eval/test_runner.py
```

Expected: all unit tests PASS.

- [ ] **Step 9: Commit**

```bash
git add shared/inference/guardrails.py \
        shared/inference/__init__.py \
        shared/eval/runner/runner.py \
        tests/shared/inference/__init__.py \
        tests/shared/inference/test_guardrails.py
git commit -m "refactor: move privacy guardrail from runner.py to shared/inference/ (C2)"
```

---

### Task 3: C3 — Fix double bundle-fetch via preflight return type

`preflight_or_raise` currently returns only `manifest`. After this change it returns `(manifest, bundle)`, eliminating the second `_fetch_bundle` call in `run_campaign`. Three files change together: `preflight.py` (signature + return), `runner.py` (`_check_trust_gate` returns dict, `run_campaign` unpacks tuple, drops standalone fetch), `test_preflight.py` (all stubs and one assertion updated).

**Files:**
- Modify: `shared/eval/runner/preflight.py`
- Modify: `shared/eval/runner/runner.py`
- Modify: `tests/shared/eval/test_preflight.py`

**Interfaces:**
- Consumes (from Task 1/2): none — no shared type changes needed.
- Produces: `preflight_or_raise(...) -> tuple[Any, dict]` where the dict is the judge bundle returned by `check_trust_gate()`.

- [ ] **Step 1: Write the failing tests in `test_preflight.py`**

`test_preflight.py` has six tests. All use `check_trust_gate=lambda: None`; that lambda now needs to return a `dict`. And `test_passes_when_all_steps_ok` doesn't assert on the return value — add an assertion.

Replace the entire content of `tests/shared/eval/test_preflight.py` with:

```python
"""Tests for the 5-step preflight."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.eval.runner.preflight import PreflightFailure, preflight_or_raise


@dataclass(frozen=True)
class FakeManifest:
    target_host: str = "mac"
    endpoint: str = "http://localhost:11434/v1"


def test_passes_when_all_steps_ok() -> None:
    fake_bundle = {"trust": {"enforcement": "lenient"}}
    manifest, bundle = preflight_or_raise(
        check_postgres=lambda: None,
        check_manifest=lambda: FakeManifest(),
        check_trust_gate=lambda: fake_bundle,
        check_rate_card=lambda h: None,
        check_endpoint_ready=lambda url, timeout_s: None,
    )
    assert isinstance(manifest, FakeManifest)
    assert bundle == fake_bundle


def test_fails_at_postgres_step() -> None:
    def boom():
        raise RuntimeError("connection refused")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=boom,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=lambda: {},
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
            check_trust_gate=lambda: {},
            check_rate_card=no_card,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "rate_card"


def test_fails_at_manifest_step() -> None:
    def boom():
        raise KeyError("no such model_id")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=boom,
            check_trust_gate=lambda: {},
            check_rate_card=lambda h: None,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "manifest"


def test_fails_at_trust_gate_step() -> None:
    def boom():
        raise NotImplementedError("strict trust gate not implemented")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=boom,
            check_rate_card=lambda h: None,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "trust_gate"


def test_fails_at_endpoint_ready_step() -> None:
    def boom(url, timeout_s):
        raise TimeoutError(f"endpoint {url} not ready within {timeout_s}s")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=lambda: {},
            check_rate_card=lambda h: None,
            check_endpoint_ready=boom,
        )
    assert ei.value.step == "endpoint_ready"
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/shared/eval/test_preflight.py -v
```

Expected: `test_passes_when_all_steps_ok` FAILS with `cannot unpack non-iterable FakeManifest`; the others pass or fail for the wrong reason (stubs returning `{}` when `None` was expected — the current code ignores the return value so they may still pass). At minimum the first test fails.

- [ ] **Step 3: Update `preflight.py`**

Replace the entire content of `shared/eval/runner/preflight.py` with:

```python
"""5-step preflight per spec §5. Step 6 (writing the initial run row) is the
caller's responsibility in runner.py."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class PreflightFailure(RuntimeError):
    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"preflight failed at step={step!r}: {cause}")
        self.step = step
        self.cause = cause


def preflight_or_raise(
    check_postgres: Callable[[], None],
    check_manifest: Callable[[], Any],
    check_trust_gate: Callable[[], dict],
    check_rate_card: Callable[[str], None],
    check_endpoint_ready: Callable[[str, float], None],
    endpoint_timeout_s: float = 60.0,
) -> tuple[Any, dict]:
    """Run all five steps in order; on failure raise PreflightFailure with step+cause.

    Returns (manifest, bundle) on success, where bundle is the dict returned by
    check_trust_gate.
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
        bundle = check_trust_gate()
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

    return manifest, bundle
```

- [ ] **Step 4: Run to verify preflight tests pass**

```bash
uv run pytest tests/shared/eval/test_preflight.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Update `runner.py`**

**Change 1** — `_check_trust_gate` returns the bundle dict instead of `None`. Change its return type annotation in the function signature (around line 276):

```python
def _check_trust_gate(judge_config_version: str, test: bool) -> dict:
    """Stub for v0.1: deterministic-only routing is always trusted.

    Sprint 3 will accept (judge_config_version, gold_set_version, ...) and
    enforce per-task kappas; for v0.1 the lenient bundle short-circuits.
    """
    bundle = _fetch_bundle(judge_config_version, test=test)
    if bundle["trust"]["enforcement"] == "lenient":
        return bundle
    raise NotImplementedError("strict trust gate arrives in Sprint 3 plan")
```

**Change 2** — In `run_campaign`, unpack the tuple returned by `preflight_or_raise` (around line 57):

```python
    try:
        manifest, bundle = preflight_or_raise(
            check_postgres=lambda: _check_postgres(test=test),
            check_manifest=lambda: resolve(model_id, test=test),
            check_trust_gate=lambda: _check_trust_gate(judge_config_version, test=test),
            check_rate_card=lambda host: load_rate_card(host),
            check_endpoint_ready=lambda url, t: None,   # Ollama exposes /v1 immediately; skip in v0.1
        )
    except PreflightFailure as f:
```

**Change 3** — Remove the standalone `bundle = _fetch_bundle(...)` line (around line 88, just after `examples = _fetch_examples(...)`):

```python
    # --- Load fixtures ---
    examples = _fetch_examples(gold_set_version, test=test)
    # DELETE the next line:
    bundle = _fetch_bundle(judge_config_version, test=test)
    cost_accountant = CostAccountant.for_target(manifest.target_host)
```

After the deletion that block becomes:

```python
    # --- Load fixtures ---
    examples = _fetch_examples(gold_set_version, test=test)
    cost_accountant = CostAccountant.for_target(manifest.target_host)
```

- [ ] **Step 6: Run all unit tests**

```bash
uv run pytest tests/shared/ -v --ignore=tests/shared/eval/test_runner.py
```

Expected: all unit tests PASS.

- [ ] **Step 7: Commit**

```bash
git add shared/eval/runner/preflight.py \
        shared/eval/runner/runner.py \
        tests/shared/eval/test_preflight.py
git commit -m "refactor: preflight_or_raise returns (manifest, bundle) — eliminate double fetch (C3)"
```

---

### Task 4: C4 — Establish `tests/integration/` directory

Moves `test_runner.py` from the unit-test tree into a dedicated `tests/integration/` directory. No import changes are needed — the file uses absolute imports throughout.

**Files:**
- Create: `tests/integration/__init__.py`
- Move: `tests/shared/eval/test_runner.py` → `tests/integration/test_runner.py`

**Interfaces:**
- Consumes: nothing — pure file move.
- Produces: `tests/integration/test_runner.py` discovered automatically by pytest (no `testpaths` restriction in pyproject.toml).

- [ ] **Step 1: Create the integration package**

```bash
touch tests/integration/__init__.py
```

- [ ] **Step 2: Move the test file**

```bash
git mv tests/shared/eval/test_runner.py tests/integration/test_runner.py
```

- [ ] **Step 3: Verify the move**

```bash
ls tests/integration/
```

Expected: `__init__.py  test_runner.py`

```bash
ls tests/shared/eval/
```

Expected: `__init__.py  test_aggregate.py  test_cost.py  test_deterministic.py  test_preflight.py` (no `test_runner.py`).

- [ ] **Step 4: Run all unit tests to confirm nothing broke**

```bash
uv run pytest tests/shared/ -v
```

Expected: all unit tests PASS (test_runner.py is no longer here so no integration DB needed).

- [ ] **Step 5: Confirm test_runner.py is still collected (dry run)**

```bash
uv run pytest tests/integration/test_runner.py --collect-only
```

Expected: pytest shows the test items in `tests/integration/test_runner.py` without errors. (The tests won't run without a live DB — `--collect-only` just confirms discovery.)

- [ ] **Step 6: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_runner.py
git rm tests/shared/eval/test_runner.py   # already staged by git mv, but explicit is safe
git commit -m "refactor: move test_runner.py to tests/integration/ (C4)"
```

---

## Self-Review

**Spec coverage:**
- C1 migration SQL ✓ (Task 1, Step 1)
- `_example_uuid()` removed from loader ✓ (Task 1, Step 4)
- `example_id::text` cast removed from runner ✓ (Task 1, Step 6)
- `enforce_privacy_guardrail` in `shared/inference/guardrails.py` ✓ (Task 2, Step 4)
- Exported from `shared/inference/__init__.py` ✓ (Task 2, Step 6)
- Runner updated to import and call public function ✓ (Task 2, Step 7)
- `preflight_or_raise` returns `(manifest, bundle)` ✓ (Task 3, Step 3)
- `check_trust_gate` type `Callable[[], dict]` ✓ (Task 3, Step 3)
- `_check_trust_gate` returns bundle ✓ (Task 3, Step 5 Change 1)
- `run_campaign` unpacks `manifest, bundle` ✓ (Task 3, Step 5 Change 2)
- Standalone `bundle = _fetch_bundle(...)` removed ✓ (Task 3, Step 5 Change 3)
- `test_preflight.py` stubs updated to return `{}` ✓ (Task 3, Step 1)
- `tests/integration/__init__.py` created ✓ (Task 4, Step 1)
- `test_runner.py` moved ✓ (Task 4, Step 2)

**Placeholder scan:** No TBD/TODO introduced. Reload step in Task 1 uses a concrete Python command with a real path. Migration SQL is complete.

**Type consistency:** `preflight_or_raise` returns `tuple[Any, dict]` in both the implementation (Task 3, Step 3) and the test that unpacks it (`manifest, bundle = preflight_or_raise(...)` in Task 3, Step 1). `_check_trust_gate` return type `-> dict` matches the `bundle = check_trust_gate()` capture in preflight.py.
