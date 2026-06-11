# Pre-Sprint-2 Cleanups Design

**Date:** 2026-06-11
**Status:** Approved

## Scope

Four deferred cleanup items from the Sprint 1 final review, to be completed before Sprint 2 begins substantive work. Items 4, 6, and 7 from the original list are explicitly deferred (S3 TODO already present in code; JudgeBundleView is a Sprint 3 concern; experiment re-run requires Spark hardware).

---

## C1 — uuid5 → Readable Text PK for `gold_example.example_id`

**Problem:** `gold_example.example_id` is stored as a `uuid5` hash of the human-readable `ex_<lane>_<suffix>` ID. The original readable string is not recoverable from the schema, making ad-hoc DB queries and result joins awkward.

**Migration strategy:** Dev DB only; truncate all data in FK order, then alter the column type.

**Migration file:** `migrations/002_gold_example_readable_id.sql`

Steps:
1. Truncate in FK order to avoid constraint violations: `judgement`, `result`, `run`, `gold_example`, `gold_set_version`.
2. `ALTER TABLE gold_example ALTER COLUMN example_id TYPE text;`
3. `ALTER TABLE result ALTER COLUMN example_id TYPE text;`

**Loader change (`shared/goldsets/loader.py`):**
- Remove `_example_uuid()` function entirely.
- Pass `ex.example_id` (the readable string) directly where `_example_uuid(ex.example_id)` was called.

**Runner change (`shared/eval/runner/runner.py`):**
- Remove the `example_id::text` cast in the `SELECT` query (it is redundant once the column is `text`).

**After migration:** Re-run the loader against the existing JSONL gold sets to repopulate the dev DB with readable PKs.

---

## C2 — Move Privacy Guardrail to `shared/inference/`

**Problem:** `_enforce_privacy_guardrail()` lives in `runner.py`. Per spec, this check belongs at the inference adapter boundary (`shared/inference/`), not in the runner. Sprint 2 will add Tier 2 endpoints; the guardrail must be in place before any Tier 2 call path is wired.

**New file:** `shared/inference/guardrails.py`
- Define `enforce_privacy_guardrail(example: GoldExample) -> None` (public name — this is now a module-level contract).
- Body is identical to the current `_enforce_privacy_guardrail` in `runner.py`.

**Export:** Add `enforce_privacy_guardrail` to `shared/inference/__init__.py` and `__all__`.

**Runner change:** Remove `_enforce_privacy_guardrail` definition from `runner.py`; import and call `enforce_privacy_guardrail` from `shared.inference`.

---

## C3 — Fix Double Bundle-Fetch

**Problem:** `_check_trust_gate()` in `runner.py` fetches the judge bundle, then `run_campaign()` fetches it again immediately after preflight returns. Two identical DB/network round-trips per campaign.

**Design (Option A — thread bundle through preflight):**

`preflight.py` changes:
- `check_trust_gate` parameter type: `Callable[[], None]` → `Callable[[], dict]`
- Capture the return value: `bundle = check_trust_gate()`
- Return type: `Any` → `tuple[Any, dict]` (manifest, bundle)
- Return `(manifest, bundle)` instead of `manifest`

`runner.py` changes:
- `_check_trust_gate()`: return the bundle it fetches instead of returning `None`.
- `run_campaign()`: unpack `manifest, bundle = preflight_or_raise(...)`.
- Remove the standalone `bundle = _fetch_bundle(judge_config_version, test=test)` line (currently line 85).

`test_preflight.py` changes:
- Update `check_trust_gate` stubs to return a dict (e.g., `lambda: {}`) where they currently return `None`.
- Assert that `preflight_or_raise` returns a tuple `(manifest, bundle)` rather than just manifest.

---

## C4 — Establish `tests/integration/` Directory

**Problem:** `tests/integration/` does not exist. `tests/shared/eval/test_runner.py` is functionally an integration test (requires real Postgres) but lives alongside unit tests.

**Changes:**
- Create `tests/integration/__init__.py` (empty).
- Move `tests/shared/eval/test_runner.py` → `tests/integration/test_runner.py`.
- No import changes required (the file uses absolute imports only).
- No pytest config changes required (`pyproject.toml` has no `testpaths` restriction; `tests/integration/` is discovered automatically).

---

## Execution Order

1. C1 (migration) — run migration, update loader + runner, reload dev DB.
2. C2 (guardrail move) — pure refactor, no schema changes.
3. C3 (bundle-fetch fix) — signature change touches preflight, runner, and tests.
4. C4 (test reorganization) — file move only.

Each item is independent; C1 must complete before re-running the loader, but the four cleanups can otherwise be implemented in any order. The recommended order above minimizes context-switching (schema work first, then code refactors, then test reorganization).

---

## Out of Scope

- `halted_judge_uncalibrated` taxonomy mapping (deferred to Sprint 3 — `TODO(S3)` already in code).
- `JudgeBundleView` adapter for JSONB decoupling (deferred to Sprint 3 when bundle schema evolves).
- Re-running experiment 0001 with a larger model (requires Spark hardware, ETA ~2026-06-15).
- pgvector, Phase 2+ schema changes, or any Sprint 2 feature work.
