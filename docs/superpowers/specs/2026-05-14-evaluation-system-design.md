# Design — Evaluation system

**Date:** 2026-05-14 (drafted 2026-05-26 from brainstorm; spec date is the planning date in PLAN.md)
**Status:** Draft v0.1 — pending user review
**Scope:** The four hard-to-reverse decisions that define the eval substrate

## Purpose

This spec defines the foundation of the sovereign eval lab — the substrate that every phase from Phase 1 onward will build on. It commits to four hard-to-reverse decisions:

1. **Inference contract** — the wire format every sovereign target (and, in Phase 8, every Tier-2 endpoint) speaks.
2. **Run-storage schema** — the Postgres model that turns each campaign into a reproducible, replayable record.
3. **Gold-set taxonomy** — the structure, storage, and immutability of the moat.
4. **Judge protocol** — how judges are routed, calibrated, trust-gated, and stress-tested.

Each of these is **hard to reverse** in the sense that every downstream phase (gold sets v0.1, judge stack, lane depth, memory, dashboards, application) is built against them. Getting them right now is worth more than getting them written quickly.

## Inputs to this design

- `ROADMAP.md` — phase definitions, acceptance criteria, the sovereignty tier breakdown, the open questions.
- `PLAN.md` — execution sequencing (Sprint 1 lays the substrate; Spark arrives at S2 start).
- `docs/superpowers/specs/2026-05-12-ai-experiments-repo-design.md` — repo conventions, area tags, Postgres-on-Mac-mini, public-repo constraint.
- `docs/planning/2026-05-12-deep-research-{chatgpt,gemini}.md` — landscape research that informed the sovereignty framing.

## Constraints settled by the brainstorm (2026-05-26)

These are the constraints under which everything below was designed. Reverse one of them and the design changes:

| Constraint | Choice | Rationale |
|---|---|---|
| **Gold-set storage** | Separate **private git repo** (`ai-experiments-goldsets`, versioned JSONL) → loaded into sovereign Postgres for serving | The public `ai-experiments` repo cannot hold private gold sets; git tags give natural immutability; Postgres serves dashboards and the runner |
| **Replay rigor** | **Pragmatic manifest** — model id + revision/quant + runtime + version + resolved sampling + target host | High reproducibility without bit-for-bit ceremony; right for a solo lab |
| **Run-store modeling** | **Pragmatic hybrid** — first-class tables (`run`, `result`, `judgement`) with typed columns + JSONB for shape-evolving fields | Indexable where it matters (filtering, charts, dashboards), flexible everywhere else |
| **Inference contract surface** | **Lean eval-focused** — `/v1/chat/completions` (non-streaming) + `/v1/embeddings`, optional `logprobs` | Defer streaming/tools/vision to the phase that needs them; additive-extensible |
| **Sovereign concerns location** | **In the eval runner**, not in the contract or its headers | One code path across Tier 1 / 2 / 3; endpoints stay pure OpenAI; runner owns cost, budget, run_id, teardown |

## Architecture

### Units

Each unit has a single purpose, a typed interface, and can be tested in isolation.

| Unit | Lives at | Responsibility | Talks to |
|---|---|---|---|
| **Inference endpoints** | One per sovereign target (Mac, Spark, cloud burst) | Serve tokens, OpenAI-compatible wire. Nothing sovereign-specific. | — (the runner calls them) |
| **Inference adapter** | `shared/inference/` | `InferenceClient(host, model)` wrapping the OpenAI HTTP API; returns a typed response. Stateless. | Inference endpoints |
| **Model registry** | `shared/models/` | Resolve `model_id → ModelManifest` from YAML files; load into Postgres at startup. | — |
| **Eval runner** | `shared/eval/runner/` | Campaign orchestration: per-example dispatch, judge dispatch, cost accumulation, budget enforcement, on-demand teardown, run-store writes. **The only place sovereign concerns live.** | Adapter · Registry · Cost accountant · Postgres |
| **Cost accountant** | `shared/eval/cost/` | Rate cards per target. Turns `usage` + wall time into cost increments. Pure function. | — |
| **Run-store** | Postgres (sovereign Mac mini) | `run`, `result`, `judgement`, plus reference tables. Source of truth. | — |
| **Gold-set loader** | `shared/goldsets/` | Read released versions from the private git repo into Postgres. Idempotent. | Private git repo · Postgres |
| **Judge stack** | Same shape as inference endpoints | Judge models are entries in `model_manifest`; judge calls go through the same inference contract. | (called by runner) |

### Big-picture diagram

```
                ┌──────────────────────────────────────────────────────────┐
                │                       eval-runner                        │
                │  resolves model_id → manifest · loops gold examples      │
                │  attaches run_id · enforces max_cost_usd · tears down    │
                │  on-demand compute · writes Postgres                     │
                └───────────┬───────────────────────────────────┬──────────┘
                            │ inference                         │ judge call
                            │ (OpenAI-compatible wire)          │ (same wire)
        ┌───────────────────┼──────────────────────┐            │
        ▼                   ▼                      ▼            ▼
  ┌──────────┐         ┌──────────┐          ┌─────────┐    ┌──────────┐
  │ Mac mini │         │   Spark  │          │  cloud  │    │  judge   │
  │   :8000  │         │   :8000  │          │  burst  │    │ endpoint │
  │ vLLM-MLX │         │ NIM/TRT  │          │ vLLM…   │    │  (same   │
  │  /ollama │         │  vLLM…   │          │         │    │ contract)│
  └──────────┘         └──────────┘          └─────────┘    └──────────┘
        ▲                   ▲                      ▲            ▲
        └───────────────────┴───── one URL pattern ─┴────────────┘
                              (differs only in host)

                            ┌───────────────────────┐
   private repo ─── load ──►│   Postgres            │
   ai-experiments-          │  - gold_set_version   │
   goldsets                 │  - gold_example       │
   (versioned JSONL,        │  - run                │
   canonical, immutable)    │  - result             │
                            │  - judgement          │
                            └───────────────────────┘
```

### Data flow for one campaign

1. `eval-runner --model qwen2.5-72b-instruct-q4 --gold-set v0.1 --judge-config v0.1 --max-cost-usd 5.00`
2. Runner resolves the model id → manifest; allocates `run_id`; writes initial `run` row with full manifest + judge_config snapshotted as JSONB.
3. Runner streams gold-set examples from Postgres (`gold_example WHERE version = v0.1`).
4. For each example: deterministically render the prompt → POST to the manifest's endpoint → store `result(run_id, example_id, rendered_prompt, response, usage, cost_increment, wall_ms)`. Cumulative cost check vs `max_cost_usd`; if exceeded → halt + teardown.
5. Dispatch judges by `(lane, expected.type)` routing in `judge_config.bundle`. Each judge call is just another inference call. Write `judgement` rows.
6. On completion: finalize the `run` row (`cost_actual_usd`, `wall_seconds`, `summary_scores`, status, teardown receipts).

**Key invariants** the architecture gives us:

- The **wire is pure OpenAI everywhere** (Tier 1 today, Tier 2 in Phase 8, judge calls always). One mental model.
- The **runner is the only place sovereign concerns live**. One code path.
- The **endpoints are swappable per target** without touching the contract or the runner.
- **Gold-set canonicality is in private git**; Postgres is a derived serving index — drop and rebuild safely.

---

## 1. Inference contract

### Endpoints

**`POST /v1/chat/completions`** — non-streaming, OpenAI-compatible.

| Request field | Required | Notes |
|---|---|---|
| `model` | ✓ | The runner sends the *resolved* model id (e.g. `qwen2.5-72b-instruct-q4`). One model per endpoint; mismatch → `404`. |
| `messages` | ✓ | Standard `{role, content}` list. `system` / `user` / `assistant` roles only in v0.1. |
| `temperature` | optional (default `0.0`) | Runner always sets explicitly. |
| `top_p` | optional (default `1.0`) | Runner always sets explicitly. |
| `max_tokens` | ✓ | Required by the runner; endpoints may impose ceilings. |
| `seed` | optional | Honored where the runtime supports it; capability flag on manifest. |
| `logprobs`, `top_logprobs` | optional | Endpoints that can't return must respond `400` with a clear error code. |
| `stop` | optional | Standard OpenAI list. |

**Out of scope for v0.1** (revisit per-phase): streaming, tool/function calling, vision/images, `response_format`, JSON mode, frequency/presence penalty. The contract is additive-extensible — adding a field will not break existing clients.

**Response:** standard OpenAI shape. The runner consumes `choices[0].message.content` and `usage = {prompt_tokens, completion_tokens, total_tokens}`. Missing/implausible `usage` triggers wall-time costing fallback with a warning on the `result` row.

**`POST /v1/embeddings`** — request `{model, input, encoding_format}` with `encoding_format=float` in v0.1; response in OpenAI shape; `usage.prompt_tokens` required.

### Model-id resolution

```yaml
# shared/models/registry/qwen2.5-72b-instruct-q4.yaml
id: qwen2.5-72b-instruct-q4
family: qwen2.5
size: 72b
revision: "2024-09-19"
quantization: q4_k_m
runtime: vllm
runtime_version: "0.6.3"
target_host: spark
endpoint: "http://spark.local:8000/v1"
capabilities: [chat, seed]
default_sampling:
  temperature: 0.0
  top_p: 1.0
  max_tokens: 1024
context_window: 32768
```

YAML files are loaded into the `model_manifest` Postgres table at startup. **The full resolved manifest is snapshotted onto every `run` row** — YAML edits do not affect prior runs.

**Convention: new revision = new id.** `qwen2.5-72b-instruct-q4-rev2024-12-01` is a different model from `qwen2.5-72b-instruct-q4`. This is the simplest defense against silent drift.

### Sampling determinism

The runner sets `temperature`, `top_p`, `max_tokens` from the manifest's `default_sampling` (or per-experiment overrides). For greedy decoding, seed-capable endpoints get one; non-seed runtimes flag `nondeterministic_runtime: true` on every result.

### Error semantics

Endpoints return `{"error": {"type", "code", "message"}}`. The runner classifies into four buckets:

| Bucket | HTTP | Runner behavior |
|---|---|---|
| **retryable** | 502 · 503 · 504 · ECONNRESET · ETIMEDOUT | 3 retries with exponential backoff (1s, 4s, 16s); then fail this example, record on result, continue |
| **client-fatal** | 400 · 404 · 422 | No retry; fail this example; surface in dashboards |
| **rate-limit** | 429 | Honor `Retry-After`; back off (10/30/60s); counts as retryable |
| **catastrophic** | unrecoverable malformed JSON · OOM in error body · repeated 5xx | Halt the campaign; finalize run as `halted_endpoint_error`; teardown |

Per-call timeout = `min(60s, manifest.context_window × 4ms)` as a starting heuristic; tune per-target.

### Health / readiness

Sovereign endpoints must expose:

- `GET /healthz` → 200 if the process is up.
- `GET /readyz` → 200 if the model is loaded and ready.

The runner blocks on `/readyz` before starting a campaign (on-demand boots can take minutes).

### Authentication

Sovereign endpoints are network-isolated; v0.1 uses no auth header on Tier 1. Endpoints accept `Authorization: Bearer …` and ignore it (keeps OpenAI-default clients happy). Tier 2 in Phase 8 brings real bearer tokens via per-provider adapters in the runner.

---

## 2. Run-storage schema

**Modeling rule:** anything used for a chart axis, a foreign key, or a hot-path filter is a typed column; everything else is JSONB.

### Reference tables (slow-changing)

**`model_manifest`** — registry-derived from `shared/models/registry/*.yaml`.

```
id              text PK
family          text
size            text
revision        text
quantization    text
runtime         text                 -- vllm | nim | trt_llm | mlx | sglang
runtime_version text
target_host     text                 -- mac | spark | cloud-burst-a3 | ...
endpoint        text
capabilities    text[]               -- chat | embeddings | seed | logprobs
context_window  int
default_sampling jsonb
raw             jsonb                -- full YAML body
loaded_at       timestamptz
```

**`gold_set_version`** — one row per released gold-set snapshot.

```
version          text PK              -- v0.1
released_at      timestamptz
git_commit_sha   text                 -- private goldsets-repo commit pinned at release
lane_counts      jsonb                -- {general: 80, sea: 60, ...}
released         bool                 -- once true, no more inserts to gold_example for this version
notes            text
```

**`gold_example`** — one row per example per version. Each version is a complete snapshot (v0.2 redeclares v0.1's still-current examples plus additions).

```
version              text   FK → gold_set_version
example_id           uuid
lane                 text   -- general | sea | japanese | ocr | finance
source               text
annotator            text
annotated_at         date
prompt_template      text   -- path within prompt_templates/; rendered deterministically with `inputs`
inputs               jsonb
expected             jsonb  -- {type: exact|set|rubric, value: ...}
provenance_tag       text   -- private | public | public-derived
never_to_third_party bool
tags                 text[]
contamination_risk   text   -- none | low | high | known-in-corpus
PRIMARY KEY (version, example_id)
INDEX (lane, version)
```

Immutability is enforced at three layers: (a) git tag on the source repo, (b) `released=true` flag, (c) a trigger that refuses inserts into `gold_example` when `gold_set_version.released=true`.

**`judge_config`** — versioned bundle (specialist, generalist, deterministic config, routing, calibration κs, rubrics).

```
version          text PK
released_at      timestamptz
bundle           jsonb       -- see Section 4 for shape
notes            text
```

### Spine (one campaign = one `run`)

**`run`**

```
id                   uuid PK
started_at           timestamptz
finished_at          timestamptz nullable
status               text  -- running | completed
                           -- | halted_budget | halted_endpoint_error
                           -- | halted_judge_uncalibrated | halted_manual | halted_setup
model_id             text  -- denormalized for dashboards
model_manifest       jsonb -- snapshot at run-time
gold_set_version     text  FK → gold_set_version
judge_config_version text  FK → judge_config
judge_config         jsonb -- snapshot at run-time
max_cost_usd         numeric(10,4)
cost_actual_usd      numeric(10,4) nullable
wall_seconds         int   nullable
n_examples_total     int
n_examples_scored    int   default 0
n_examples_errored   int   default 0
summary_scores       jsonb nullable    -- per-lane aggregates, written at finalize
experiment_id        text  nullable
notes                text  nullable
error                jsonb nullable    -- populated on halt
INDEX (status, started_at)
INDEX (model_id, started_at)
INDEX (gold_set_version)
```

The JSONB snapshots of `model_manifest` and `judge_config` are the replay guarantee: even if the underlying YAML or bundle is later edited, the run row is self-contained.

**`result`** — one per example per run.

```
id                       uuid PK
run_id                   uuid FK → run
example_id               uuid
gold_set_version         text          -- denormalized; (gold_set_version, example_id) → gold_example
rendered_prompt          text          -- the exact prompt sent; essential for replay verification
response                 text nullable
response_logprobs        jsonb nullable
usage                    jsonb         -- {prompt_tokens, completion_tokens}
cost_increment_usd       numeric(10,6)
wall_ms                  int
score                    numeric(6,4) nullable    -- aggregated final (see Section 4 aggregation)
score_kind               text         nullable    -- binary | scalar | rubric_aggregate
error_class              text nullable             -- retryable_exhausted | client_fatal | catastrophic | judge_parse_failed
error_body               jsonb nullable
nondeterministic_runtime bool default false
started_at               timestamptz
finished_at              timestamptz
INDEX (run_id)
INDEX (run_id, example_id)
INDEX (run_id) WHERE error_class IS NOT NULL
```

`score` + `score_kind` carry the aggregated judgement (computed per Section 4 aggregation rule) so leaderboard / dashboard queries don't need to join `judgement` on the hot path. The per-judge audit trail stays in `judgement`.

**`judgement`** — one per (result, judge).

```
id                  uuid PK
result_id           uuid FK → result
judge_role          text  -- specialist | generalist | deterministic | external_recalibration
judge_manifest      jsonb -- snapshot of judge's model manifest (or deterministic config)
rubric_id           text  nullable
rendered_prompt     text  nullable     -- null for deterministic
raw_response        text  nullable
score               numeric(6,4) nullable    -- nullable if parse_error
score_kind          text                     -- binary | scalar | rubric_aggregate
rationale           text nullable
parse_error         bool default false
usage               jsonb nullable
cost_increment_usd  numeric(10,6)
wall_ms             int
created_at          timestamptz
INDEX (result_id)
INDEX (result_id, judge_role)
```

### Replay primitive

Given `run.id`:

1. Read `run.model_manifest`, `run.gold_set_version`, `run.judge_config` from the row (the snapshots — *not* the FK targets).
2. For each example in `gold_example WHERE version = run.gold_set_version`:
   - Re-render the prompt from `prompt_template` + `inputs`.
   - Diff against the stored `result.rendered_prompt`. **A mismatch is a bug** (template-renderer drift or storage corruption); halt with a clear error.
   - Re-invoke the endpoint with the manifest's sampling. With `temperature=0` + a seed-capable runtime, expect bit-identical `response`. Otherwise distributional equivalence; record a `replay_run` whose `notes` contains `replay_of=<original_id>`.
3. Re-invoke judges from the snapshotted `judge_config`.

Replay is itself a new `run` row, so comparing the two is just SQL.

### Migrations

Plain SQL files under `migrations/001_init.sql`, `002_*.sql`, …, applied by a small Python applier (~20 LOC) tracking applied IDs in a `schema_migrations` table. No alembic / sqitch / liquibase ceremony until the project demands it. Per the ROADMAP instrumentation track, the rationale for each migration is recorded in `docs/notes/instrumentation.md`.

### Cost precision

`cost_increment_usd numeric(10,6)` (micro-cent precision for per-call increments) summed into `run.cost_actual_usd numeric(10,4)` (≤ $999,999.9999 — far more than any single run will ever cost).

---

## 3. Gold-set taxonomy + private-git ↔ Postgres pipeline

The private repo is the canonical source of truth and the immutability anchor (via git tags); Postgres is a derived serving index that can be dropped and rebuilt. **Curation work happens in the private repo; runtime queries happen in Postgres.**

### Private repo: `ai-experiments-goldsets`

```
ai-experiments-goldsets/                  # PRIVATE; separate from the public ai-experiments repo
├── README.md                             # contributor doc (the curation pipeline)
├── versions/
│   ├── v0.1/                             # read-only by convention after tag
│   │   ├── manifest.yaml                 # version metadata + lane counts + commit-sha self-ref
│   │   ├── general.jsonl
│   │   ├── sea.jsonl
│   │   ├── japanese.jsonl
│   │   ├── ocr.jsonl
│   │   ├── finance.jsonl
│   │   └── checksums.txt                 # sha256 per lane file
│   └── v0.2/ …
├── prompt_templates/                     # Jinja2; versioned WITH the gold set
│   ├── general/reasoning.j2
│   └── sea/ · japanese/ · ocr/ · finance/
├── seeds/                                # pre-release working area; never loaded into Postgres
├── public_subsets/                       # explicitly-public mirrored releases (Phase 8 / recalibration)
│   └── v0.1/ …
└── tools/
    ├── validate.py                       # schema check; runs in pre-commit
    └── release.py                        # cuts a new version (validate → write manifest+checksums → tag)
```

Each `versions/vN.M/` directory is a **complete snapshot**, not an additive diff. Storage cost is trivial at this scale; reasoning is dramatically simpler than diff-based versioning.

`gold_set_version.git_commit_sha` pins the exact source-repo commit for each released version.

### Per-example JSONL record

```jsonc
{
  "example_id": "ex_general_001a2b3c",      // stable across versions; ex_<lane>_<8-hex>
  "lane": "general",
  "source": "manually curated; analog of ...",
  "annotator": "jonathan",
  "annotated_at": "2026-05-29",
  "prompt_template": "general/reasoning.j2",
  "inputs": { "question": "...", "context": "..." },
  "expected": {                             // discriminated union by type
    "type": "rubric",                       // exact | set | rubric
    "value": {
      "rubric_id": "reasoning-multi-step-v1",
      "expected_answer": "...",
      "key_steps": ["...", "..."]
    }
  },
  "provenance_tag": "private",              // private | public | public-derived
  "never_to_third_party": true,
  "tags": ["arithmetic", "multi-hop"],
  "contamination_risk": "none"              // none | low | high | known-in-corpus
}
```

**ID scheme:** `ex_<lane>_<8-hex>` — lane-prefixed uuid4 truncation. Stable for the life of the example across versions.

**`expected` is a discriminated union:** `exact` and `set` route to the deterministic scorer; `rubric` routes to the specialist judge (see Section 4).

### Prompt templates

Jinja2 templates under `prompt_templates/<lane>/<name>.j2`, **versioned with the gold set** (same private repo, same tag). The runner renders deterministically from `example.prompt_template` + `example.inputs`, stores the result on `result.rendered_prompt`. **Template changes require a new gold-set version.**

### Curation pipeline (seed → expand → filter → annotate → review → release)

| Stage | Where | Operation |
|---|---|---|
| **Seed** | `seeds/<lane>-draft.jsonl` | Drop candidate items in; loose JSONL, edited freely. |
| **Expand** | `seeds/` | Paraphrase / variant-generate where the lane calls for it. |
| **Filter** | `seeds/` | Deduplicate, drop low-quality, set `contamination_risk` per source. |
| **Annotate** | argilla *or* label-studio (Phase 2 bake-off in `experiment 0006`) | Annotator fills `expected`, `tags`, `rubric_id`. Tool exports back to JSONL. |
| **Review** | `seeds/` | Second-pair review (or solo + checklist); disagreements logged in `docs/notes/calibration.md`. |
| **Release** | `tools/release.py v0.X` | Validates schema, assembles `versions/v0.X/`, writes `manifest.yaml` + `checksums.txt`, commits, tags `goldsets-v0.X`. |

Annotation tooling stays **tool-agnostic in this spec** — whichever wins Phase 2's bake-off must produce records matching the JSONL schema. That's the only contract.

### Public/private split

- **Default**: `provenance_tag=private`, `never_to_third_party=true`. The runner adapter refuses to dispatch such examples to Tier-2/3 endpoints (a guardrail in `shared/inference/`, checked at adapter boundary; surfaces as `halted_setup` with `privacy_violation`).
- **Public-derived items** (e.g. FinanceBench public split, JFinQA public split): `provenance_tag=public`, `never_to_third_party=false`.
- **`public_subsets/v0.X/`**: explicitly-mirrored public-only releases built by `tools/release.py --public-only`. The only path by which any gold-set data can reach Tier-2/3 (used in Phase 8 cost benchmark and any external recalibration).

### Loader: `shared/goldsets/`

```python
load_version(version="v0.1", repo_path="/Users/.../ai-experiments-goldsets")
```

Reads `versions/v0.1/*.jsonl`, validates against schema, INSERTs `gold_set_version` (with `git_commit_sha = HEAD`), INSERTs `gold_example` rows, sets `released=true`.

- **Idempotent**: re-running on the same `(version, sha)` is a no-op with a log line.
- **Refuses inconsistent re-release**: same `version` with a different sha is an error — versions are immutable.
- Runs at Mac-mini startup and on-demand from CLI; never in the request path.

### Contamination tagging

Advisory, not structural. The structural defense is the sovereign inference path; the tag is for analytic lenses:

- Dashboards can filter by contamination tier ("score on uncontaminated subset only").
- New-model evaluations get a per-lane breakdown by contamination risk.
- Items in known training corpora (e.g. canonical FinanceBench items) are tagged `known-in-corpus` and reported with-and-without.

### OCR-lane images (forward-looking)

OCR examples will reference images by sha256 (`inputs.image_sha256`); image bytes live in a sovereign image store (initially a folder on the Mac mini). Out of scope for v0.1 but the schema reserves `inputs.image_sha256` so the OCR lane lands cleanly later.

---

## 4. Judge protocol

A judge is just a model in the registry; a judge call is a vanilla inference call. What needs design is the **protocol on top**: routing, aggregation, calibration, bias stress, and trust enforcement.

### Routing

```
expected.type                    →  judges that fire
─────────────────────────────────────────────────────────────────
exact   (e.g. multi-choice, numeric)  →  deterministic
set     (e.g. set-membership, F1)     →  deterministic
rubric  (open-ended, criteria-scored) →  specialist
─────────────────────────────────────────────────────────────────
lane override (in judge_config):
  finance × arithmetic_followup       →  deterministic + specialist
  general × open_reasoning            →  specialist + generalist (periodic)
```

Single-judge is the default and keeps cost predictable; multi-judge is opt-in per `(lane, expected_type)` in the bundle.

### `judge_config.bundle` shape (JSONB snapshotted on `run.judge_config`)

```yaml
version: v0.1
released_at: 2026-...
routing:
  by_expected_type:
    exact:  [deterministic]
    set:    [deterministic]
    rubric: [specialist]
  by_lane_override:
    finance.arithmetic_followup: [deterministic, specialist]
judges:
  deterministic:
    config:
      string_normalize: [lowercase, strip_punct, whitespace_collapse]
      numeric_tolerance_abs: 1e-6
      numeric_tolerance_rel: 1e-3
  specialist:
    model_id: prometheus2-8x7b-q4
    rubric_set: rubrics_v0.1
  generalist:
    model_id: qwen2.5-72b-instruct-q4
    protocol: g_eval_v1
aggregation:
  rule: weighted_mean
  tie_break: deterministic
  weights: {deterministic: 1.0, specialist: 0.7, generalist: 0.3}
calibration:
  human_calibration_set: human_calibration_v0.1
  kappa_threshold: 0.80
  per_task_kappa:
    specialist__general__reasoning-multi-step-v1: 0.84
    specialist__finance__arithmetic-followup-v1: 0.81
    generalist__general__open_reasoning-v1: 0.76        # below threshold → not trusted
    specialist__japanese__finance-v1: null              # not yet measured
trust:
  enforcement: strict                       # strict | lenient
rubrics:
  reasoning-multi-step-v1:
    prompt_template: rubrics/reasoning-multi-step-v1.j2
    criteria:
      - {id: correctness,     weight: 0.5, scale: 1-5}
      - {id: reasoning_steps, weight: 0.3, scale: 1-5}
      - {id: clarity,         weight: 0.2, scale: 1-5}
    aggregation: weighted_mean
notes: ...
```

Rubrics live inside the bundle (they describe how judges score, not what's in the gold set). Changing a rubric = new bundle version.

**Where the source lives:** Unlike gold sets, the judge bundle is **not** private — it's algorithmic configuration. Bundle source YAML lives in the public repo at `shared/eval/judges/configs/<version>.yaml`; the `prompt_template` path inside each rubric resolves relative to `shared/eval/judges/rubrics/` in the same repo. `tools/release_judge_config.py` validates the YAML, runs the bias stress tests (below), and on pass INSERTs the bundle row into Postgres.

### Aggregation

- **Tie-break by deterministic** — when deterministic fires alongside an LLM judge, its 1/0 *replaces* the aggregated score; the LLM judgement is still stored for audit but doesn't affect the result.
- **Otherwise weighted-mean** — scalar scores normalized to 0–1: `aggregated = Σ(weight_i × score_i) / Σ(weight_i)`. Binary: weighted majority.
- **Per-judge judgements are always stored** in `judgement`; the aggregated value is materialized on `result.score` + `result.score_kind` (the addendum to Section 2's spine schema).

### Calibration set

Same private repo, sibling to `versions/`:

```
ai-experiments-goldsets/
└── human_calibration/
    └── v0.1/
        ├── manifest.yaml
        ├── examples.jsonl
        └── annotators.yaml
```

Each calibration record:

```jsonc
{
  "example_id": "ex_general_001a2b3c",
  "gold_set_version": "v0.1",
  "human_judgement": { "score": 1.0, "rationale": "..." },
  "annotator_a": { "id": "jonathan", "score": 1.0, "rationale": "..." },
  "annotator_b": { "id": "second-reviewer", "score": 1.0, "rationale": "..." },
  "agreement": "agreed",                    // agreed | resolved | unresolved
  "resolution_notes": null
}
```

### κ measurement workflow

For each `(judge_role, lane, rubric_id)` tuple:

1. Run the judge against every calibration example matching `(lane, rubric)`.
2. Compare its score to `human_judgement.score`.
3. Compute Cohen's κ (weighted κ for scalar scales).
4. Write the value into the next bundle's `calibration.per_task_kappa`.

`tools/calibrate_judge_config.py` does this end-to-end and outputs a YAML diff to apply. Re-runs are cheap on cached calibration outputs.

### Trust gate (enforced at run start)

```python
def can_run_lane(lane, gold_examples_in_lane, judge_config):
    # Enumerate every (expected_type, rubric_id) pair actually used in this lane.
    # rubric_id is None for `exact` / `set` examples; the trust key falls back to expected_type.
    tasks = {
        (ex.expected.type, ex.expected.value.get("rubric_id"))
        for ex in gold_examples_in_lane
    }
    for expected_type, rubric_id in tasks:
        routing = judge_config.routing_for(lane, expected_type)
        for judge_role in routing:
            if judge_role == "deterministic":
                continue
            key = f"{judge_role}__{lane}__{rubric_id or expected_type}"
            kappa = judge_config.calibration.per_task_kappa.get(key)
            if kappa is None:
                return False, f"no κ measured for {key}"
            if kappa < judge_config.calibration.kappa_threshold:
                return False, f"κ={kappa:.2f} < threshold for {key}"
    return True, None
```

Any failure in **strict** mode → `status=halted_judge_uncalibrated` at run start (no inference calls made). **Lenient** mode downgrades to a warning on `run.notes`; useful for Phase 2 bootstrapping when calibration is still being built. Default is strict from Phase 3 onward.

### Bias stress tests

Three tests, all under `experiments/0012-eval-judge-bias-stress/`:

| Test | Probe | Metric | Gate |
|---|---|---|---|
| **Position bias** | Pairwise comparisons with order swapped | ∆score when only order flips | per-bundle threshold |
| **Length bias** | Short-correct vs long-wrong pairs (and inverse) | Length-correlation on judgement | per-bundle threshold |
| **Discrimination** | Known-quality-ordered pairs | % correctly ranked | per-bundle floor |

Results in `docs/notes/judge-biases.md`. `tools/release_judge_config.py` runs all three as a pre-release gate.

### Judge invocation — the call path

For one example whose routing returns `[specialist]`:

```
runner
  → looks up rubric from judge_config.bundle.rubrics[rubric_id]
  → renders the rubric's judgement prompt with {example, model_output, expected.value}
  → POSTs /v1/chat/completions to the specialist's endpoint (from its model_manifest)
  → parses structured response { score, rationale, per_criterion }
  → writes a `judgement` row
```

Judges return structured output (JSON inside the assistant content). The runner has a small `parse_judgement(raw, protocol)` per judgement protocol (`g_eval_v1`, specialist rubric format, ...). Parse failures → `judgement.score=null, parse_error=true`; aggregation falls back to remaining judges; if none succeed, `result.error_class=judge_parse_failed` and the campaign continues.

### External recalibration (Tier-3 closed-API)

ROADMAP working bias: "exclude unless drift actually shows up." Codified:

- **Default**: closed-API judges (Tier 3) are not invoked.
- **Trigger**: if a sovereign judge's measured κ drifts > 0.05 below its documented value over a rolling window of N bundle releases, the next bundle release MAY include an external recalibration pass.
- **Mechanism**: `tools/external_recalibrate.py --provider <openai|anthropic|gemini> --gold-set <vN.M-public-subset>` — gated by `--gold-set` being a `public_subsets/` build, so private examples cannot leak.
- **Result**: stored as `judgement` rows with `judge_role=external_recalibration`; never used in production aggregation; consulted only for drift diagnosis.

---

## 5. Error handling, observability, testing

### Run statuses (single source of truth)

| Status | Trigger | Side effects |
|---|---|---|
| `running` | Run started, in flight | — |
| `completed` | All examples scored, finalized | `summary_scores` written |
| `halted_budget` | `cost_actual_usd ≥ max_cost_usd` after a result | Teardown invoked |
| `halted_endpoint_error` | Catastrophic endpoint error | Teardown invoked |
| `halted_judge_uncalibrated` | Strict-mode trust gate failed at start | No teardown needed |
| `halted_manual` | User Ctrl-C or `kill --run-id` | Teardown invoked |
| `halted_setup` | Pre-flight failed | Teardown if any boot already happened |

### Pre-flight (before the first inference call)

```
1. Postgres reachable & schema_migrations current
2. model_manifest resolves locally & matches what Postgres knows
3. judge_config trust gate passes for every (lane × expected.type) in the gold set
4. cost_accountant.has_rate_card(manifest.target_host) == True
5. on-demand target booted & /readyz==200 (with manifest's timeout)
6. write initial `run` row with status=running
```

Failures at step 2 onward → `halted_setup` with the failed step on `run.error`; **the `run` row is written before any inference call**, so failed attempts after step 1 are recorded. Failures at step 1 (Postgres unreachable) cannot be recorded in the run-store by definition; those surface only in stderr logs and the runner exits non-zero — surfaced via the runner's invocation environment, not the run-store.

### Error path by component

| Component | Failure mode | Behavior |
|---|---|---|
| **Inference endpoint** | Retryable 5xx / connection error | 3 retries with exp backoff |
| | 429 rate-limit | Honor `Retry-After`; 3 backoffs (10/30/60s) |
| | 4xx client-fatal | Fail this example, record `error_class=client_fatal`, **continue** |
| | Catastrophic | `halted_endpoint_error` |
| **Cost accountant** | Missing `usage` | Wall-time costing fallback + warn |
| | No rate card for `target_host` | `halted_setup` |
| **Judge parser** | Malformed structured output | `judgement.score=null, parse_error=true`; aggregation falls back |
| | All judges parse-failed for a result | `result.error_class=judge_parse_failed`; **continue** |
| **Judge endpoint** | Same as inference endpoint | Same classification |
| **Manifest resolver** | YAML missing/invalid/capability mismatch | `halted_setup` |
| **Goldset loader** | Checksum mismatch | Refuse to load; alert; exit non-zero |
| | Same `version` with different sha | Refuse; immutability violation |
| **Privacy guardrail** | `never_to_third_party=true` → Tier-2/3 endpoint | Refuse at adapter; `halted_setup` (privacy_violation) |
| **On-demand teardown** | Cloud API call fails | Log loudly; `run.notes += teardown_failed: <reason>`; don't block status finalization |
| **Postgres write** | Transient failure | Retry; persistent → `halted_endpoint_error` (cause: postgres_unreachable) |
| **Replay** | `rendered_prompt` mismatch | Halt immediately; never silently swallow |

### Observability

- **Stderr** (JSON lines) for tailing during development. One line per result + status transitions.
- **Postgres** is the durable source of truth. No external metrics store in v0.1.
- Per-run summary printed at finalize: status, cost vs budget, per-lane scores, n_errored, p50/p95 wall_ms.

### Testing strategy

Three rings, scaled to cost.

**Unit (pytest, fully mocked, fast)**

| Module | Tests |
|---|---|
| `shared/inference/` | error classification by HTTP code; retry/backoff; payload shape |
| `shared/models/` | YAML loading + validation; manifest resolution; capability checks |
| `shared/eval/cost/` | rate-card math; usage-missing fallback; precision |
| `shared/eval/runner/` | per-example dispatch; budget check; status transitions; trust gate; pre-flight ordering |
| `shared/eval/judges/` | `g_eval_v1` parser; specialist rubric parser; aggregation (single, multi, deterministic tie-break) |
| `shared/goldsets/` | schema validation; idempotent load; immutability refusal; checksum verification |

**Integration (pytest with real Postgres + mock OpenAI server)**

| Test | Asserts |
|---|---|
| Happy-path campaign | 3 examples × tiny model × deterministic → `completed`, rows correct, cost reasonable |
| **Replay** | Re-run with seed; `rendered_prompt` byte-identical; with seed-capable runtime, `response` byte-identical |
| Budget halt | Cost trigger mid-stream → `halted_budget`, teardown called, partial results preserved |
| Trust gate (strict) | Missing κ → `halted_judge_uncalibrated`, no inference calls |
| Privacy guardrail | Private example + Tier-2 → `halted_setup`, no calls |
| Schema migrations | Apply all `migrations/*.sql` on fresh DB; idempotent on second apply |

**Property-based replay (Hypothesis, pre-release)**

Generate arbitrary `(example, manifest, judge_config)` tuples; run twice with seed; assert `rendered_prompt` and `response` match. Catches subtle determinism regressions.

**Real-endpoint smoke (rare, manual, before tagging a phase)**

One small live model on the Mac mini, 3-example public subset, end-to-end; targets the Phase 1 "one URL, three hosts" claim. Lives in `experiments/0001-inference-blessed-sovereign-runtime/`.

**Bias stress tests** — Section 4; gate `tools/release_judge_config.py`.

### CI

Per the repo-design spec, CI/CD is out of scope for now. v0.1 runs all of the above locally with `uv run pytest`. The suite is built CI-ready (no env-specific assumptions, Postgres via fixture); when CI becomes warranted (likely alongside Phase 6's leaderboard), wiring GitHub Actions is a one-day task and not a substrate change.

### One-glance threat model

| Risk | Defense |
|---|---|
| Silent model drift (e.g. Llama 3.1 → 3.1.1) | "New revision = new id" + manifest snapshot on `run` |
| Manifest YAML edited later | `run.model_manifest` is a JSONB snapshot, not FK |
| Private example sent off-sovereign | Adapter guardrail blocks `never_to_third_party=true` at Tier-2/3 |
| Judge κ drift unnoticed | Per-bundle κ + runtime strict trust gate |
| Cost overrun | Per-result budget check + halt + teardown |
| Replay produces different output | Stored `rendered_prompt` diff at replay-start; halt-on-mismatch |
| Gold-set version drift | `released=true` trigger + git tag + checksums |
| Endpoint crash mid-campaign | Catastrophic → `halted_endpoint_error`; partial results retained |
| Postgres outage mid-run | Retry; persistent → catastrophic; partial state preserved on `run` |

---

## Acceptance criteria mapped

### Phase 1 — Sovereign inference substrate

- ✅ *"One URL pattern differs only in host"* — all sovereign endpoints expose the same `/v1/chat/completions` + `/v1/embeddings`; only `endpoint` on the manifest changes.
- ✅ *"Any past run fully reconstructable from stored state — no handcrafted prompts"* — `result.rendered_prompt` + snapshotted manifest + snapshotted judge_config.
- ✅ *"Every eval run records its cost"* — `result.cost_increment_usd`, summed into `run.cost_actual_usd`.
- ✅ *"Campaigns that exceed `max_cost_usd` halt and tear down on-demand compute automatically"* — runner cumulative check after each result; `halted_budget` + teardown hook.

### Phase 2 — Gold sets v0.1

- ✅ *"~250–400 examples in v0.1 across 5 lanes"* — `gold_set_version.lane_counts`; targeted in Phase 2 work.
- ✅ *"Each example has [the 8 fields]"* — 1:1 in the JSONL schema and `gold_example` columns.
- ✅ *"Curation pipeline documented; fresh contributor can use it"* — table in Section 3; lives in the private repo's README.
- ✅ *"v0.1 immutable; adds go to v0.2"* — git tag + `released=true` + Postgres trigger.

### Phase 3 — Sovereign judge stack

- ✅ *"Specialist + generalist + deterministic deployed behind the inference contract"* — judges are `model_manifest` entries; called via `/v1/chat/completions`.
- ✅ *"100–200 human-calibration examples, double-annotated"* — `human_calibration/vN.M/` with `annotator_a` + `annotator_b` + `agreement`.
- ✅ *"Each judge has a κ score per task type; only κ ≥ 0.8 trusted"* — `per_task_kappa` keyed by `(judge_role, lane, rubric)`; strict trust gate.
- ✅ *"Bias stress tests pass above documented thresholds"* — position / length / discrimination + release gate.

### Phases 4–8 — relevant substrate guarantees

- Lane depth (Phase 4) adds rows to `gold_example` under new versions and adds rubrics to `judge_config`. No substrate change.
- Memory (Phase 5) adds `shared/memory/` adapter; integrates with the run-store as additional context provided to inference calls (no contract change).
- Eval Lab v1 (Phase 6) — the one-hour onboarding test is an integration test on this exact substrate; dashboards read from `run`/`result`/`judgement`.
- Application (Phase 7) — reuses contract, gold sets, judges, run-store as the spec mandates.
- Tier-2 cost benchmark (Phase 8) — Tier-2 endpoints drop in via per-provider adapters in the runner; the contract is unchanged.

---

## Open follow-ups (not blocking this spec)

- **Private goldsets repo creation** — `ai-experiments-goldsets` does not yet exist on GitHub. **Prerequisite** for any gold-set work (Phase 2 start). One-time setup.
- **Blessed sovereign runtime on Spark** (ROADMAP open question) — NIM vs TRT-LLM vs vLLM as default. Decided in `experiments/0001-inference-blessed-sovereign-runtime/` (Phase 1 bake-off).
- **Sovereign judge models** (ROADMAP open question) — Prometheus 2 vs Atla Selene for specialist; Qwen 2.5 72B vs Llama 3.3 70B for generalist. Decided in experiments `0009`–`0010` (Phase 3 bake-offs).
- **Annotation tool** — argilla vs label-studio. Decided in `experiment 0006` (Phase 2 bake-off). Spec is tool-agnostic; whichever wins, its export must match the JSONL schema.
- **Default on-demand sovereign target** — GCE A3 / AWS P5 / Runpod / Lambda. Decided by Sprint 3 per PLAN.
- **Dashboard stack** — Grafana on Postgres vs custom Next.js. Decided in Phase 6.
- **External recalibration trigger threshold** — currently "κ drift > 0.05 over rolling window of N releases"; both the threshold and N to be tuned with first calibration data.
- **OCR image store** — folder vs object-store as the substrate matures. Out of scope for v0.1; schema reserves `inputs.image_sha256`.

---

## Prerequisites for the implementation plan

When this spec moves to implementation planning (writing-plans skill, after user review), the plan must scaffold:

1. **`ai-experiments-goldsets` private GitHub repo** — one-time creation; README, `versions/`, `prompt_templates/`, `seeds/`, `public_subsets/`, `tools/`, `human_calibration/` skeletons.
2. **`shared/inference/`** — `InferenceClient`, error classification, retry/backoff.
3. **`shared/models/`** — registry YAML loader, manifest resolver, Postgres sync.
4. **`shared/goldsets/`** — JSONL schema validator, idempotent loader.
5. **`shared/eval/cost/`** — rate-card loader, cost calculation.
6. **`shared/eval/runner/`** — campaign orchestration, pre-flight, budget enforcement, teardown hook interface.
7. **`shared/eval/judges/`** — judge invocation, protocol parsers, aggregation.
8. **`migrations/001_init.sql`** — the seven tables in Sections 2 and 3.
9. **`tools/release.py`** (in private repo) and **`tools/release_judge_config.py`** (in public repo).
10. **Postgres + pgvector on the Mac mini** — Week 1 Mon task from PLAN.
11. **Experiment `0001-inference-blessed-sovereign-runtime/`** — first end-to-end use of the substrate; selects the blessed Spark runtime.

These map to Sprint 1 of PLAN.md, with the Spark-dependent items pushed to Sprint 2 (after the Spark arrives ~Jun 15).
