# Tranche 1 Repository Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a truthful, lint-clean repository baseline and preserve a fresh Mac smoke run under the current schema.

**Architecture:** This tranche makes no product-behavior changes. It first removes the eight known lint violations, then reconciles the living planning documents with observed repository and database state, and finally reruns experiment 0001 against local Ollama so replay evidence exists after migration 002.

**Tech Stack:** Python 3.12, Ruff, pytest, PostgreSQL 17, Ollama, Markdown, git.

## Global Constraints

- Do not start cloud resources in this tranche.
- Do not change runtime behavior while fixing lint.
- Phase 1 stays `in progress` until the cloud and automatic-teardown gates pass.
- Phase 2 is `in progress`; Argilla is the selected annotation tool.
- Phase 3 is `in progress` only at the uncalibrated generalist-judge integration level.
- Actual experiment folders are canonical; unstarted roadmap items do not receive numeric IDs.
- Preserve the fresh smoke run in the development database after verification.
- Run the complete test suite and complete Ruff check before the tranche is complete.

---

### Task 1: Restore a clean Ruff baseline

**Files:**
- Modify: `shared/goldsets/argilla_export.py`
- Modify: `tests/shared/eval/test_lm_judge.py`
- Modify: `tests/shared/goldsets/test_argilla_export.py`
- Modify: `tests/shared/goldsets/test_validate_seed.py`

**Interfaces:**
- Consumes: existing Python modules and tests.
- Produces: identical behavior with `uv run ruff check .` returning exit code 0.

- [ ] **Step 1: Capture the known failing lint baseline**

Run:

```bash
uv run ruff check .
```

Expected: exit code 1 with exactly eight findings: six unused imports and two `E741` ambiguous-variable findings.

- [ ] **Step 2: Remove only the unused imports**

Apply these exact import changes:

```python
# shared/goldsets/argilla_export.py
# Delete:
from pydantic import ValidationError
# Replace:
from shared.goldsets.schema import GoldExample, SeedExample
# With:
from shared.goldsets.schema import SeedExample
```

```python
# tests/shared/eval/test_lm_judge.py
# Replace:
from unittest.mock import MagicMock, patch
# With:
from unittest.mock import MagicMock
```

```python
# tests/shared/goldsets/test_argilla_export.py
# Delete:
import pytest
from pathlib import Path
```

```python
# tests/shared/goldsets/test_validate_seed.py
# Delete:
import pytest
```

- [ ] **Step 3: Rename both ambiguous comprehension variables**

In `tests/shared/goldsets/test_argilla_export.py`, replace both occurrences of:

```python
rows = [json.loads(l) for l in out_file.read_text().strip().splitlines()]
```

with:

```python
rows = [json.loads(line) for line in out_file.read_text().strip().splitlines()]
```

- [ ] **Step 4: Run the affected tests**

Run:

```bash
uv run pytest tests/shared/eval/test_lm_judge.py tests/shared/goldsets/test_argilla_export.py tests/shared/goldsets/test_validate_seed.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run the full lint gate**

Run:

```bash
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit the lint-only change**

```bash
git add shared/goldsets/argilla_export.py \
  tests/shared/eval/test_lm_judge.py \
  tests/shared/goldsets/test_argilla_export.py \
  tests/shared/goldsets/test_validate_seed.py
git commit -m "chore: restore clean ruff baseline"
```

---

### Task 2: Reconcile the roadmap and execution plan

**Files:**
- Modify: `ROADMAP.md`
- Modify: `PLAN.md`
- Modify: `EXPERIMENTS.md`
- Create: `docs/notes/rebaseline-2026-07-18.md`

**Interfaces:**
- Consumes: the observed repository state summarized in `docs/superpowers/specs/2026-07-17-operational-recovery-design.md`.
- Produces: planning documents that distinguish implemented scaffolding from live operational evidence.

- [ ] **Step 1: Add the rebaseline revision to `PLAN.md`**

Change the version line to:

```markdown
**Version:** v1.2 — drafted 2026-05-14, revised 2026-07-18 (operational recovery; calendar converted to historical baseline plus dependency gates)
```

Add this revision-log entry above the 2026-05-26 entry:

```markdown
- **2026-07-18 — operational rebaseline (v1.1 → v1.2).** Sprint 2 produced substantial code scaffolding for GCP inference, the sovereign judge, and Argilla, but did not produce live cloud campaigns or annotated gold-set volume. The 2026-07-06 → 2026-07-26 Sprint 3 window is no longer a credible Phase 2 release date. The original calendar remains below as historical intent; current execution follows the recovery gates in `docs/superpowers/specs/2026-07-17-operational-recovery-design.md`: repository recovery → safe cloud smoke → reviewed general-lane slice → remaining lanes → calibration.
```

- [ ] **Step 2: Mark the sprint table as historical and add current gates**

Immediately before the sprint table, add:

```markdown
> **Rebaseline note (2026-07-18):** The table below is the original scheduling baseline, not the current forecast. Do not infer completion from elapsed dates. Current work advances only when the following gates pass.

| Recovery gate | Status on 2026-07-18 | Exit condition |
|---|---|---|
| Repository recovery | in progress | full pytest and Ruff clean; current planning state committed; Mac smoke and replay preserved |
| Safe cloud lifecycle | planned | private-tunnel L4 and A100 smoke runs recorded; automatic Terraform teardown proven; final GCP inventory empty |
| General-lane curation slice | planned | 10 submitted and independently reviewed examples, including at least 2 rubric examples, exported and test-loaded |
| Gold-set v0.1 | blocked on curation | all 5 lanes meet targets and quality gates; immutable version tagged |
| Judge calibration | blocked on reviewed rubrics | specialist/generalist calibration set double-annotated; kappa and bias gates pass |
```

- [ ] **Step 3: Close resolved `PLAN.md` decisions**

Replace the annotation-tool item with:

```markdown
- [x] **Annotation tool decided (2026-07-11): Argilla v2.** The self-hosted workflow and CLI are implemented; live annotation remains part of the recovery gates.
```

Replace the cloud-provider item with:

```markdown
- [x] **Cloud burst provider decided (2026-07-11): GCP.** L4 inference and A100 judge workspaces are scaffolded in `infra/gcp/`; live smoke validation and teardown remain open.
```

Leave unrelated open items unchanged.

- [ ] **Step 4: Update Phase 1 status and experiment list in `ROADMAP.md`**

Replace the Phase 1 status paragraph with:

```markdown
**Status:** in progress (started 2026-05-27; rebaselined 2026-07-18). The Mac substrate is implemented and was validated by experiment `0001-inference-contract-validation`. GCP Terraform and model manifests are scaffolded but have not yet produced a preserved live campaign. Replay under the current schema, private-tunnel cloud execution, and automatic teardown are still required.
```

Replace the Phase 1 experiment bullets with:

```markdown
- `0001-inference-contract-validation` — Mac inference contract, run store, deterministic judge, and runner smoke; complete, pending current-schema rerun evidence.
- `inference-blessed-sovereign-runtime` — choose and commission the default Spark runtime after the hardware arrives.
- `inference-private-cloud-smoke` — validate the same contract on a measured GCP L4 target through an SSH tunnel.
- `eval-run-storage-replay` — reconstruct a randomly selected preserved run from stored state.
- `eval-cost-discipline-teardown` — prove budget halting and automatic destruction of on-demand compute.
```

- [ ] **Step 5: Update Phase 2 and Phase 3 status in `ROADMAP.md`**

Replace Phase 2 status with:

```markdown
**Status:** in progress (started 2026-07-11; rebaselined 2026-07-18). The Argilla choice, seed schema, curation CLI, five lane directories, and GCP annotation workspace are implemented. Only 10 candidate seeds exist, no reviewed `annotated.jsonl` exists, and `v0.1` has not been released.
```

Replace Phase 3 status with:

```markdown
**Status:** in progress (started 2026-07-11; rebaselined 2026-07-18). Rubric routing, judge persistence, a Qwen 2.5 72B manifest, and an uncalibrated v0.2 bundle exist in code. No live sovereign-judge campaign, specialist bake-off, human calibration set, kappa gate, or bias stress result exists yet.
```

- [ ] **Step 6: Remove provisional numeric IDs from every unstarted roadmap experiment**

Keep `0001-inference-contract-validation` because its folder exists. For every other experiment bullet in Phases 2-9, remove the four-digit prefix and keep the descriptive slug. Examples of the required transformation:

```markdown
- `0005-eval-curation-workflow` — ...
```

becomes:

```markdown
- `eval-curation-workflow` — ...
```

Apply this to every unstarted experiment bullet so no future folder ID is reserved before folder creation. Verify with:

```bash
rg -n '`[0-9]{4}-' ROADMAP.md
```

Expected: the only match is `0001-inference-contract-validation`.

- [ ] **Step 7: Clarify the experiment index contract**

Add this paragraph after the opening paragraph in `EXPERIMENTS.md`:

```markdown
Only experiments with an actual `experiments/NNNN-<area>-<slug>/` folder receive an ID and a row here. Roadmap ideas remain unnumbered until their folder is created; infrastructure or workflow scaffolding alone is not an experiment result.
```

Update experiment 0001's result to:

```markdown
| 0001 | inference | inference-contract-validation | done | 2026-05-27 | Mac substrate validated in May; current-schema rerun and replay evidence tracked by the July recovery |
```

- [ ] **Step 8: Write the dated rebaseline note**

Create `docs/notes/rebaseline-2026-07-18.md` with exactly these sections and facts:

```markdown
# Operational rebaseline — 2026-07-18

## Why this exists

The calendar advanced from Sprint 1 to Sprint 3 while operational evidence did not. Code scaffolding for GCP inference, Argilla, and rubric judging landed, but the development database still contained only the three-example Mac smoke set and no current run rows. This note separates implemented software from exercised capability.

## Observed baseline

- Repository: clean `main`; no open pull requests, issues, release tags, or additional branches at the 2026-07-14 catch-up.
- Tests: 102 passed on 2026-07-14; Ruff had eight cleanup findings before Tranche 1.
- Development DB: migrations 001 and 002 applied; one Mac manifest; judge bundle v0.1; smoke-v0.0 with three examples; zero preserved runs after migration 002 truncated development data.
- Gold sets: two candidate seeds in each of five lanes; no annotated JSONL and no v0.1 tag.
- GCP inventory: no instances, persistent disks, reserved addresses, or buckets in `adept-prod-497323` when checked on 2026-07-15.
- Cloud configuration: L4, A100 judge, and Argilla Terraform workspaces exist but have not been validated live; model and judge endpoints still require the private-tunnel recovery changes.

## Decision

Execution is dependency-gated rather than date-gated: restore the repository baseline, prove private cloud execution and teardown, complete a reviewed ten-example general slice, then expand lanes and begin calibration. Phase 4 and memory work remain paused.

## What counts as progress

Generated candidates, mocked tests, Terraform files, and elapsed sprint dates are reported separately from reviewed examples, live campaigns, destroyed infrastructure, and calibrated judges. Only the latter satisfy phase acceptance gates.
```

- [ ] **Step 9: Check documentation consistency**

Run:

```bash
rg -n 'Phase 2.*planned|Phase 3.*planned|Annotation tool.*\[ \]|Cloud burst provider.*\[ \]' ROADMAP.md PLAN.md
rg -n '`[0-9]{4}-' ROADMAP.md
git diff --check
```

Expected: the first command returns no stale matches; the second returns only experiment 0001; `git diff --check` returns no errors.

- [ ] **Step 10: Commit the rebaseline documents**

```bash
git add ROADMAP.md PLAN.md EXPERIMENTS.md docs/notes/rebaseline-2026-07-18.md
git commit -m "docs: rebaseline recovery gates and phase status"
```

---

### Task 3: Recreate current-schema Mac smoke evidence

**Files:**
- Modify: `experiments/0001-inference-contract-validation/README.md`
- Runtime state: local Ollama and development PostgreSQL only; no committed database files.

**Interfaces:**
- Consumes: model `qwen2.5:0.5b-instruct`, judge bundle v0.1, `smoke-v0.0`, migration 002, and `experiments/0001-inference-contract-validation/run.sh`.
- Produces: one preserved completed run with three results and three deterministic judgements in the development database.

- [ ] **Step 1: Verify local dependencies**

Run:

```bash
/Library/PostgreSQL/17/bin/pg_isready -h /tmp -d ai_experiments -U huiliang
curl -fsS http://127.0.0.1:11434/api/tags
```

Expected: PostgreSQL reports `accepting connections`; Ollama returns JSON containing `qwen2.5:0.5b-instruct`.

If Ollama is not running, run:

```bash
brew services start ollama
```

Then repeat the health check. Do not pull a different model in this tranche.

- [ ] **Step 2: Apply and list migrations**

Run:

```bash
uv run python -m shared.db.migrations apply
uv run python -m shared.db.migrations list
```

Expected: no unapplied migrations; both 001 and 002 are listed as applied.

- [ ] **Step 3: Sync the local manifest and v0.1 bundle**

Run:

```bash
uv run python -c "from shared.models.registry import sync_all; print(sync_all())"
uv run python -c "from shared.eval.judges import register_bundle; register_bundle('v0.1'); print('registered v0.1')"
```

Expected: manifest sync completes and the bundle command prints `registered v0.1`.

- [ ] **Step 4: Ensure the smoke set is loaded idempotently**

Run:

```bash
uv run python -c "from pathlib import Path; from shared.goldsets.loader import load_jsonl_to_postgres; print(load_jsonl_to_postgres(Path('experiments/0001-inference-contract-validation/seed.jsonl'), 'smoke-v0.0', '4aacf2f04ac221c66c1cc3db0bfc7ffcddab5121'))"
```

Expected: `0` when the existing immutable smoke version is present, or `3` only if it had not yet been loaded.

- [ ] **Step 5: Run the live Mac campaign**

Run:

```bash
experiments/0001-inference-contract-validation/run.sh
```

Expected: output contains a new `run_id`, `status=completed`, `scored=3`, and `errored=0`.

- [ ] **Step 6: Verify persisted replay inputs and judgements**

Run this read-only query:

```bash
/Library/PostgreSQL/17/bin/psql -h /tmp -d ai_experiments -U huiliang -P pager=off -c "WITH latest AS (SELECT id FROM run WHERE experiment_id = '0001-inference-contract-validation' ORDER BY started_at DESC LIMIT 1) SELECT r.status, r.model_id, r.gold_set_version, r.judge_config_version, r.n_examples_scored, count(DISTINCT x.id) AS results, count(DISTINCT j.id) AS judgements, bool_and(x.rendered_prompt IS NOT NULL) AS prompts_preserved, bool_and(r.model_manifest IS NOT NULL) AS manifest_preserved FROM run r JOIN latest l ON l.id=r.id LEFT JOIN result x ON x.run_id=r.id LEFT JOIN judgement j ON j.result_id=x.id GROUP BY r.id;"
```

Expected: one row with `completed`, `smoke-v0.0`, `v0.1`, 3 scored, 3 results, 3 judgements, and both preservation booleans true.

- [ ] **Step 7: Document the fresh rerun without overwriting the May result**

Append a `## Current-schema verification — 2026-07-18` section to the experiment README. Record the exact emitted run ID, status, cost, scored count, errored count, and the replay-query row. State explicitly that the May run was removed by migration 002's development-data truncation and that this rerun is the preserved replacement.

- [ ] **Step 8: Run final repository verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
git diff --check
```

Expected: all tests pass, Ruff reports `All checks passed!`, and the diff check is clean.

- [ ] **Step 9: Commit the updated experiment evidence**

```bash
git add experiments/0001-inference-contract-validation/README.md
git commit -m "docs: preserve current-schema Mac smoke evidence"
```
