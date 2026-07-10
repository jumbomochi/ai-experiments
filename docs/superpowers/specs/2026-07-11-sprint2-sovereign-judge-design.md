# Sprint 2 — Sovereign Judge Stack on GCP

**Date:** 2026-07-11
**Status:** Approved

## Context

The DGX Spark has not yet arrived. Sprint 2 pivots to GCP as the sovereign compute anchor for all Spark-dependent work. The eval substrate (Mac mini, Phase 1) is complete. This spec covers: (1) extending the GCP Terraform stack to an A100-class instance for large-model inference and judging, (2) deploying Qwen 2.5 72B AWQ as the sovereign generalist judge, and (3) wiring the runner to route `expected.type == "rubric"` examples through the LLM judge.

Runs in parallel with the Gold-Set Curation Pipeline spec (2026-07-11-sprint2-goldset-curation-design.md).

---

## Section 1 — Infrastructure

The judge gets its own Terraform workspace — `infra/gcp/judge/` — separate from the existing eval-model workspace in `infra/gcp/`. Separate state means independent `make up/down` for judge vs inference instances; both can run simultaneously during a campaign.

**Instance:** `a2-highgpu-1g` — 1× A100 40 GB VRAM, `asia-southeast1`. With vLLM `--gpu-memory-utilization 0.95` and `--max-model-len 4096`, Qwen 2.5 72B AWQ INT4 (~36 GB weights) fits comfortably.

**Judge model:** `Qwen/Qwen2.5-72B-Instruct-AWQ` — ROADMAP-preferred generalist judge, INT4 quantized, open weights. Served via vLLM behind the existing OpenAI-compatible contract, hit the same way as any eval model.

**GCS cache:** Shares the existing `ai-experiments-model-cache` bucket. Weights stored under `gs://<bucket>/Qwen/Qwen2.5-72B-Instruct-AWQ/`. Same sentinel-based cache logic (`${BUCKET}/${MODEL_ID}/.cache_complete`) as the eval startup script.

**Privacy guardrail:** `cloud-burst-a2` is already in `_TIER1_HOSTS` in `shared/inference/guardrails.py` — no changes needed.

**New files:**

| File | Purpose |
|---|---|
| `infra/gcp/judge/main.tf` | `a2-highgpu-1g` instance, firewall TCP 8000, static IP, reference existing GCS bucket |
| `infra/gcp/judge/variables.tf` | `project_id`, `zone` (default `asia-southeast1-b`), `judge_model_id`, `judge_model_revision`, `vllm_version`, `hf_token` (sensitive), `preemptible` (default `true`) |
| `infra/gcp/judge/outputs.tf` | `judge_endpoint_url` (`http://<static-ip>:8000/v1`), `instance_name` |
| `infra/gcp/judge/startup.sh.tpl` | GCS cache check + flat HuggingFace download + vLLM Docker run + 5-min health-gate |
| `infra/gcp/judge/.gitignore` | `*.tfstate`, `*.tfstate.backup`, `.terraform/`, `*.tfvars` |
| `infra/gcp/judge/Makefile` | `make judge-up`, `make judge-down`, `make judge-health`, `make judge-ssh` |
| `shared/models/registry/qwen2.5-72b-instruct-awq-vllm-a2.yaml` | Model manifest, `target_host: cloud-burst-a2`, endpoint placeholder, `runtime: vllm` |

**No new rate card needed:** `shared/eval/cost/rate_cards/cloud-burst-a2.yaml` already exists (`wall_usd_per_hour: 2.50`).

**`shared/models/manifest.py`:** No changes needed — `cloud-burst-a2` already in the `target_host` Literal.

---

## Section 2 — Judge Protocol

**New `expected.type` value:** `"rubric"` routes to the LLM judge. The `expected` column is already JSONB — no migration needed.

**Gold example `expected` field shape for rubric examples:**
```json
{
  "type": "rubric",
  "rubric": "Award 1.0 if the answer correctly identifies the country and gives a valid reason. Award 0.5 if only the country is correct. Award 0.0 otherwise.",
  "reference": "Singapore, because it has the highest GDP per capita in SEA."
}
```
`reference` is optional — some rubrics are self-contained.

**Judge prompt template** (Jinja2, stored in the judge bundle under `judges.lm_judge.rubric_template`):
```
You are a strict evaluator. Score the response below using the rubric.

### Question
{{ question }}

### Response
{{ response }}

{% if reference %}### Reference answer
{{ reference }}
{% endif %}

### Rubric
{{ rubric }}

Reply in this exact format:
SCORE: <number between 0.0 and 1.0>
RATIONALE: <one sentence>
```

**Score parsing:** Regex `SCORE:\s*([\d.]+)` on the raw response. If parsing fails: `judgement.parse_error = true`, `judgement.score = NULL`, `result.error_class = "judge_parse_failed"`.

**The `judgement` table already has all required columns** (`rendered_prompt`, `raw_response`, `rationale`, `parse_error`, `usage`, `cost_increment_usd`, `wall_ms`) — no migration needed.

**Judge bundle additions** — the existing `judge_config.bundle` JSONB gains a `judges.lm_judge` key. A new v0.2 bundle is registered alongside the unchanged v0.1 bundle:

```json
{
  "judges": {
    "deterministic": { "config": { "strip_whitespace": true, "case_sensitive": false } },
    "lm_judge": {
      "model_id": "Qwen/Qwen2.5-72B-Instruct-AWQ",
      "endpoint": "http://<judge-ip>:8000/v1",
      "rubric_template": "<Jinja2 string above>",
      "max_tokens": 128,
      "temperature": 0.0
    }
  },
  "aggregation": { "weights": { "deterministic": 1.0, "lm_judge": 1.0 } },
  "trust": { "enforcement": "lenient" }
}
```

A new `register_bundle("v0.2", test=False)` call seeds this into Postgres. The v0.1 bundle (deterministic-only) remains valid and unchanged — campaigns using it never touch the LLM judge path.

---

## Section 3 — Runner Integration

Three focused changes; all in existing files.

**1. Routing in the scoring loop (`runner.py`)**

The existing `if expected.type in {"exact", "set"}:` block gains an `elif`:

```python
elif expected.type == "rubric":
    judgement_row = _lm_judge_score(
        response_text, expected, bundle, manifest
    )
    agg_score, agg_kind = aggregate(
        [judgement_row], bundle["aggregation"]["weights"]
    )
```

`_lm_judge_score` is a new private helper in `runner.py`. It:
1. Renders the Jinja2 rubric template from `bundle["judges"]["lm_judge"]["rubric_template"]`
2. Calls the judge vLLM endpoint via the existing `InferenceClient` (constructed from `bundle["judges"]["lm_judge"]` config)
3. Parses score with regex; extracts rationale
4. Returns a `Judgement` dataclass

If `"lm_judge"` is absent from the bundle (v0.1 bundle), the `elif` branch is unreachable — no behaviour change for existing campaigns.

**2. Judge client and cost accounting**

The judge is an OpenAI-compatible vLLM endpoint — the existing `InferenceClient` handles it unchanged. Cost per judge call is measured by wall time × `wall_usd_per_hour` from the `cloud-burst-a2` rate card, written to `judgement.cost_increment_usd`. The campaign's `cost_actual_usd` (and budget-halt logic) counts only the eval model cost — judge cost lands in `judgement` rows only.

**3. Writing the judgement row**

`_write_judgement_row` already accepts `rendered_prompt`, `raw_response`, `rationale`, `usage`, `cost_increment_usd`, `wall_ms` — those fields are passed in from `_lm_judge_score`. No schema changes.

**New/modified files:**

| File | Change |
|---|---|
| `shared/eval/runner/runner.py` | Add `elif expected.type == "rubric":` routing + `_lm_judge_score` helper |
| `shared/eval/judges/__init__.py` | Add `register_bundle_v2` (or update `register_bundle` to accept version arg) seeding the v0.2 bundle |
| `tests/shared/eval/test_lm_judge.py` | New: unit tests for `_lm_judge_score` — happy path, parse failure, missing reference field |
| `tests/integration/test_runner.py` | Add rubric-type example to fixture; assert `judgement.score` is set and `judgement.raw_response` is populated |

**No new migration needed.**

---

## Execution Order

1. `infra/gcp/judge/` Terraform workspace — instance, firewall, startup script, Makefile.
2. Model manifest `qwen2.5-72b-instruct-awq-vllm-a2.yaml` (placeholder endpoint).
3. v0.2 judge bundle registered in Postgres (dev + test).
4. Runner: `_lm_judge_score` helper + routing + `_write_judgement_row` updates.
5. Tests: `test_lm_judge.py` unit tests + integration test update.
6. Smoke test: `make judge-up` → fill endpoint in manifest → `make judge-health` → run one rubric-type example through the runner → `make judge-down`.

---

## Out of Scope

- Specialist judge (Prometheus 2 / Atla Selene) — Phase 3 bake-off; deferred until gold-set v0.1 has rubric examples to calibrate against.
- Human-calibration set and Cohen's κ measurement — Sprint 3.
- Multi-judge aggregation (weighted ensemble) — current `aggregation.weights` schema supports it; not exercised until Sprint 3.
- A3 (H100) tier — Literal already includes `cloud-burst-a3`; manifest + rate card follow after A2 smoke tests pass.
- AWS — out of scope (GCP only per Sprint 2 decision).
