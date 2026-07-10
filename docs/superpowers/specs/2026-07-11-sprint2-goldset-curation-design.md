# Sprint 2 — Gold-Set Curation Pipeline

**Date:** 2026-07-11
**Status:** Approved

## Context

Phase 2 of the ROADMAP targets gold-set v0.1: ~250–400 examples across five lanes (general reasoning · SEA languages · Japanese · OCR/VLM · finance), versioned, immutable on release, with provenance tracked per example. This spec scopes Sprint 2's contribution to that goal: annotation tooling on GCP (argilla v2), a five-stage curation pipeline with CLI, and v0.1 lane targets (~150 examples).

Runs in parallel with the Sovereign Judge Stack spec (2026-07-11-sprint2-sovereign-judge-design.md). The only integration point is at the end: `rubric`-type examples require the LLM judge to be running before they can be scored in eval campaigns.

---

## Section 1 — Annotation Tooling

**Choice: Argilla v2** — Python-first, dataset-centric, exports to JSONL natively. Self-hosted on a small GCP VM so annotation sessions are not tied to the Mac being on.

**GCP instance:** `e2-standard-2` (2 vCPU, 8 GB RAM), 30 GB persistent disk, `asia-southeast1`. Not preemptible — annotation sessions require stable access. Cost: ~$0.07/hr (~$50/month while active).

**Deployment:** Docker Compose (argilla server + its Postgres backend), started via GCE startup script. Firewall opens TCP 6900 (argilla UI). Static IP so the URL is stable across stop/start cycles. Separate Terraform workspace: `infra/gcp/annotation/`.

**Argilla dataset structure:** one dataset per lane (`lane-general`, `lane-sea`, `lane-japanese`, `lane-finance`, `lane-ocr-vlm`). Each record maps to one gold example.

Fields shown to the annotator (read-only context):

| Argilla field | Content |
|---|---|
| `rendered_prompt` | The full rendered prompt the model will see |
| `source` | Where the example came from |

Questions the annotator fills in:

| Argilla question | Maps to gold example field |
|---|---|
| `expected_type` (choice: exact / set / rubric) | `expected.type` |
| `expected_value` (text) | `expected.value` or rubric text |
| `reference_answer` (text, optional) | `expected.reference` (for rubric type) |
| `never_to_third_party` (bool) | Privacy flag |
| `tags` (multi-label) | e.g. `smoke`, `hard`, `multilingual` |
| `contamination_risk` (choice: none / low / high) | `contamination_risk` |

**New code in `shared/goldsets/`:**

| File | Purpose |
|---|---|
| `argilla_push.py` | Reads seed JSONL, creates lane dataset in argilla if absent, pushes unannotated records; idempotent on `example_id` |
| `argilla_export.py` | Pulls `submitted` records from argilla, validates each against `GoldExample` schema, writes `annotated.jsonl`; exits non-zero on any validation failure |
| `validate_seed.py` | Validates a seed JSONL against the seed schema (inputs only — no `expected` required); run before push |
| `cli.py` | Thin CLI wrapper (see pipeline section) |

**New Terraform files:**

| File | Purpose |
|---|---|
| `infra/gcp/annotation/main.tf` | `e2-standard-2` instance, 30 GB disk, static IP, firewall TCP 6900 |
| `infra/gcp/annotation/variables.tf` | `project_id`, `zone`, `argilla_username`, `argilla_password` (sensitive) |
| `infra/gcp/annotation/outputs.tf` | `argilla_url` (`http://<static-ip>:6900`) |
| `infra/gcp/annotation/startup.sh.tpl` | Install Docker, write `docker-compose.yml`, `docker compose up -d` |
| `infra/gcp/annotation/Makefile` | `make up`, `make down`, `make backup` (argilla Postgres → GCS snapshot) |
| `infra/gcp/annotation/.gitignore` | `*.tfstate`, `*.tfstate.backup`, `.terraform/`, `*.tfvars` |

---

## Section 2 — Curation Pipeline

Five stages: two human-driven, three automated.

```
seed → push → annotate → export → load
```

**Stage 1 — Seed (human):** Write `gold_sets/<lane>/seed.jsonl`. Each line has inputs only — no `expected` yet. Minimum required fields: `example_id`, `lane`, `source`, `annotator`, `annotated_at`, `prompt_template`, `inputs`, `provenance_tag`. Run `validate-seed` before proceeding.

**Stage 2 — Push (`argilla_push.py`):** Reads seed JSONL, creates the lane dataset in argilla if absent, pushes records as unannotated. Idempotent — records with an existing `example_id` are skipped, so re-running after adding new seeds is safe.

**Stage 3 — Annotate (human, in argilla UI):** Annotator fills in `expected_type`, `expected_value`, `reference_answer` (if rubric), `never_to_third_party`, `tags`, `contamination_risk` per record. A second review pass marks records `submitted`. Only `submitted` records proceed to export.

**Stage 4 — Export (`argilla_export.py`):** Pulls all `submitted` records from the lane dataset, constructs a `GoldExample` for each (validating against the Pydantic schema), writes `gold_sets/<lane>/annotated.jsonl`. Exits non-zero if any record fails validation — prevents a malformed annotation from entering the pipeline silently.

**Stage 5 — Load:** Existing `load_jsonl_to_postgres` unchanged. Takes `annotated.jsonl`, a version string (e.g. `v0.1`), and a git SHA. Idempotent on `(version, sha)`.

**CLI (`shared/goldsets/cli.py`):**

```bash
uv run python -m shared.goldsets.cli validate-seed gold_sets/general/seed.jsonl
uv run python -m shared.goldsets.cli push --lane general --argilla-url http://<ip>:6900
uv run python -m shared.goldsets.cli export --lane general --out gold_sets/general/annotated.jsonl
uv run python -m shared.goldsets.cli load --file gold_sets/general/annotated.jsonl --version v0.1
```

**Gold sets directory layout (committed to repo):**

```
gold_sets/
  general/
    seed.jsonl          # inputs only — committed freely
    annotated.jsonl     # exported from argilla — committed on release only
  sea/
    seed.jsonl
  japanese/
    seed.jsonl
  finance/
    seed.jsonl
  ocr-vlm/
    seed.jsonl
```

`annotated.jsonl` files are committed only at version release (the immutable snapshot event). `seed.jsonl` files evolve freely between releases.

**`GoldExample` schema changes:** The existing `Expected` Pydantic model only has `type` and `value`. Adding `rubric` support requires:
- `value: str | list[str] | None = None` (optional — absent for rubric type)
- `rubric: str | None = None` (the scoring rubric text)
- `reference: str | None = None` (optional reference answer for rubric type)
- A validator that enforces: `exact`/`set` types require `value`; `rubric` type requires `rubric`; `reference` is always optional.

This is a one-file change to `shared/goldsets/schema.py`; no DB migration (column is already JSONB).

---

## Section 3 — Lane Targets

**Target: ~150 examples across 5 lanes for gold-set v0.1.**

| Lane | Target | `expected.type` mix | Priority | Notes |
|---|---|---|---|---|
| `general` | 40 | 80% exact, 20% rubric | 1 | Extend the existing smoke example; clearest ground truth; calibration baseline for the judge |
| `sea` | 35 | 60% exact, 40% rubric | 2 | SEA-HELM / SeaExam style; BM, TH, VI, ID, TL; factual + reasoning mix |
| `japanese` | 30 | 50% exact, 50% rubric | 3 | JFinQA-style; CJK rendering check needed in argilla before annotation starts |
| `finance` | 25 | 40% exact, 60% rubric | 4 | FinanceBench / TAT-QA style; where the LLM judge earns its keep |
| `ocr-vlm` | 20 | 70% exact, 30% rubric | 5 | Last — `inputs` JSONB holds image paths; scope-limited in v0.1 to text-extraction tasks |

**Quality gates before a lane is released:**

- Minimum 20 examples (hard floor — below this the lane score is statistically meaningless).
- Every `exact`-type example independently verified: the correct answer is confirmed by a second check, not just annotator intuition.
- Every `rubric`-type example has a reference answer AND a rubric a second person can apply consistently.
- `never_to_third_party` correctly set on every example; anything from private documents or containing PII is flagged `true`.
- `load_jsonl_to_postgres` run against the test DB without errors before the version is marked released.

**v0.1 release definition:** all five lanes at or above their targets, all quality gates passed, `gold_set_version.released = true` in Postgres for `v0.1`, `annotated.jsonl` files committed under a git tag.

---

## Execution Order

1. `infra/gcp/annotation/` Terraform workspace — VM, Docker Compose, Makefile.
2. `shared/goldsets/validate_seed.py`, `argilla_push.py`, `argilla_export.py`, `cli.py`.
3. `gold_sets/` directory with `seed.jsonl` stubs for all five lanes.
4. `make up` → validate and push `general` lane seed → annotate first ~40 examples → export → load to dev DB.
5. Repeat for remaining lanes in priority order.
6. Final: all lanes at target → quality gate pass → tag `gold-set-v0.1`.

---

## Out of Scope

- Annotation tool bake-off (argilla vs label-studio) — argilla is decided per PLAN.md.
- Multi-annotator inter-annotator agreement (Cohen's κ) — Sprint 3, after the human-calibration set is built.
- Fine-grained provenance graph (beyond `source` + `provenance_tag`) — deferred.
- OCR/VLM multimodal inputs beyond text extraction (e.g. full page images, handwriting) — v0.2+. v0.1 OCR/VLM examples use `{"image_url": "gs://..."}` in `inputs` JSONB; the runner does not resolve these in Sprint 2 (annotation-only, not yet runnable through the eval loop).
- Gold-set v0.2 (additions past v0.1) — open-ended after v0.1 releases.
- Public gold-set subsets — Phase 8 only, for the Tier 2 cost benchmark.
