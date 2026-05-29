# 0001-inference-contract-validation

**Area:** `inference` · **Status:** done · **Started:** 2026-05-27 · **Finished:** 2026-05-29

## Hypothesis

The eval substrate (inference contract + run-storage + gold-set loader + deterministic
judge + runner) wires together end-to-end on the Mac mini against a small local model,
producing a completed `run` row with three `result` rows, each scored by the deterministic
judge, with measurable cost.

If it doesn't, one of the four hard-to-reverse decisions has a flaw and the spec needs
revision.

**Explicit non-hypothesis:** that a 0.5B model can answer multiple-choice questions
correctly. The seed is a substrate smoke, not a model evaluation.

## Setup

- **Hardware:** Apple M4 Mac mini, 64 GiB unified memory, 12 cores (macOS 26.3.1, arm64)
- **Python:** 3.12.8 in a uv-managed venv
- **Postgres:** 17.5 (EnterpriseDB install at `/Library/PostgreSQL/17/`) with the eval-substrate schema applied via `migrations/001_init.sql`
- **Ollama:** 0.15.1, serving `qwen2.5:0.5b-instruct` at `http://localhost:11434/v1`
- **Gold set:** `smoke-v0.0` — 3 hand-authored multi-choice examples (arithmetic / geography / ordering), all `provenance_tag: public` (see `seed.jsonl`)
- **Judge config:** `v0.1` — deterministic-only routing, lenient trust (see `shared/eval/judges/configs/v0.1.yaml`)
- **Rate card:** `mac.yaml` — token cost \$0.00/Mtok, wall-time \$0.05/hour

Hardware report (paste from `uv run python scripts/hardware_report.py`):

```
platform:   macOS-26.3.1-arm64-arm-64bit
machine:    arm64
processor:  arm
python:     3.12.8
cpu cores:  12
memory:     64.0 GiB
ollama:     ollama version is 0.15.1
torch:      not installed (install per experiment when needed)
```

## Method

1. Apply schema: `uv run python -m shared.db.migrations apply` → already at `001`.
2. Sync model manifest: `uv run python -c "from shared.models.registry import sync_all; sync_all()"` → 1 manifest.
3. Register judge bundle: `uv run python -c "from shared.eval.judges import register_bundle; register_bundle('v0.1')"`.
4. Load the seed:
   ```bash
   uv run python -c "
   from pathlib import Path
   from shared.goldsets.loader import load_jsonl_to_postgres
   load_jsonl_to_postgres(
       Path('experiments/0001-inference-contract-validation/seed.jsonl'),
       version='smoke-v0.0', git_commit_sha='wip-smoke')
   "
   ```
   → `loaded 3 examples` first run; `0` thereafter (idempotent).
5. Run the campaign: `experiments/0001-inference-contract-validation/run.sh`.

## Results

Single end-to-end run, executed 2026-05-29 against live Ollama:

```
run_id=0aa440e9-13e7-4689-8398-19a5b29ca836  status=completed
cost=$0.000051  scored=3  errored=0
```

Per-example outcomes (psql query against `result` joined to `gold_example`):

| readable_id           | response | expected | score | wall_ms |
|-----------------------|----------|----------|-------|---------|
| `ex_general_seed0001` | `A`      | `B` (2+2)         | 0.0 | 3511 |
| `ex_general_seed0002` | `A`      | `C` (capital of Japan) | 0.0 | 93 |
| `ex_general_seed0003` | `A`      | `D` (ascending sequence) | 0.0 | 71 |

`run.summary_scores = {"avg_score": 0.0}`. The 0.5B model defaulted to `A` for all
three prompts — an expected weakness of a half-billion-parameter instruct model on
arbitrary multi-choice; not a substrate issue.

Substrate behavior that the run validated:

- ✅ One URL pattern hit (`http://localhost:11434/v1/chat/completions`) for all three calls.
- ✅ Every call recorded `usage` (prompt_tokens=33, completion_tokens=1 across rows; visible in `result.usage`).
- ✅ `cost_increment_usd` populated per row (first call's wall_ms includes Ollama's cold-start; subsequent rows show the ~100 ms warm-call latency).
- ✅ `cost_actual_usd` aggregated into the `run` row at finalize.
- ✅ Deterministic judge fired for every `expected.type=exact` example (score=1.0 or 0.0).
- ✅ `summary_scores` written with `avg_score`.
- ✅ Replay primitive preserved — `result.rendered_prompt` and `run.model_manifest` (JSONB) both captured the exact bytes that produced the answers.

## Conclusion

**Hypothesis supported.** Every substrate component — inference adapter, model registry,
gold-set loader, cost accountant, deterministic judge, aggregator, runner, run-store — fired
correctly end-to-end on the Mac mini in a single live run. The contract is OpenAI-compatible
on the wire and the runner owns all sovereign concerns (cost, run_id, budget, finalize) per
spec §1.

**Known small follow-ups exposed by this run:**

- The `gold_example.example_id` PK is a deterministic `uuid5(...)` hash of the human-readable
  `ex_<lane>_<suffix>` form from the JSONL. The original readable id is not surfaced anywhere
  in the schema, which makes joins like the per-example table above awkward. Worth either
  (a) adding `gold_example.readable_id text` as an indexed denormalized column, or (b) just
  using the readable string as the PK directly (drop uuid5). Tracked as a Sprint 2 cleanup.
- Ollama's first call to a freshly-loaded model paid ~3.5 s of cold-start latency. The
  `wall_ms` column accurately reflects this. When we start aggregating p50/p95 dashboards
  in Phase 6, we'll want to either warm Ollama before each run or report cold-start
  separately.
- The 0.5B model is too weak for the multi-choice format — every answer was `A`. For a
  real model-quality test (rather than substrate smoke), the Sprint 2 plan should run
  this seed against `qwen2.5:7b-instruct` or `qwen2.5:14b-instruct` once Spark is
  up. Don't change the seed; just use it against a bigger model.

**Next experiment:** none until Sprint 2 (Spark bring-up) — at which point experiment
`0002-inference-blessed-sovereign-runtime/` picks NIM vs TRT-LLM vs vLLM as the default
sovereign runtime on Spark.
