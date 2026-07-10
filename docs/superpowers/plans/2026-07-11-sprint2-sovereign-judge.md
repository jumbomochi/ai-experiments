# Sprint 2 — Sovereign Judge Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Qwen2.5-72B-Instruct-AWQ on a GCP A100 instance and wire the eval runner to route `expected.type == "rubric"` examples through it.

**Architecture:** Separate Terraform workspace in `infra/gcp/judge/` provisions an `a2-highgpu-1g` GCE instance. The runner gains a `_lm_judge_score` private helper that renders a Jinja2 rubric prompt, calls the judge endpoint via `InferenceClient`, and returns a `Judgement` with all DB columns populated. A new v0.2 bundle YAML replaces the `rubric: [specialist]` stub with `lm_judge` config; `Expected.rubric` and `Expected.reference` fields are added to `schema.py`.

**Tech Stack:** Terraform ~> 5.0 (Google provider), GCE `a2-highgpu-1g` (A100 40 GB), vLLM Docker, Jinja2, Pydantic v2 `model_validator`, pytest with `unittest.mock`.

## Global Constraints

- Terraform provider: `hashicorp/google ~> 5.0` — same as `infra/gcp/`
- vLLM extra flags for A100 judge: `--max-model-len 4096 --gpu-memory-utilization 0.95`
- Judge model: `Qwen/Qwen2.5-72B-Instruct-AWQ` — INT4 AWQ, served via vLLM OpenAI-compatible API
- GCS bucket: shared existing bucket `${project_id}-ai-experiments-model-cache` — referenced via `data` source, NOT created
- Judge host constant: `_JUDGE_HOST = "cloud-burst-a2"` (already in `_TIER1_HOSTS`)
- `_write_judgement_row` must write `rendered_prompt`, `raw_response`, `rationale`, `usage`, `cost_increment_usd`, `wall_ms` — these columns already exist in the `judgement` table (001_init.sql)
- Judge cost lands ONLY in `judgement.cost_increment_usd` — NOT in campaign `cost_actual_usd` / budget-halt logic
- Score regex: `SCORE:\s*([\d.]+)` — clamp result to `[0.0, 1.0]`
- No new DB migrations — all columns exist
- `test=True` throughout for test-mode DB operations
- All Python files: `from __future__ import annotations` as second line (after module docstring)
- v0.2 bundle registered with the existing `register_bundle(version, test)` — no code change to `judges/__init__.py`
- YAGNI: do not add multi-judge aggregation, strict trust enforcement, or specialist judge

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `infra/gcp/judge/main.tf` | Create | `a2-highgpu-1g` instance, firewall TCP 8000, static IP, data-source GCS bucket |
| `infra/gcp/judge/variables.tf` | Create | 7 variables incl. `judge_model_id`, `judge_model_revision` |
| `infra/gcp/judge/outputs.tf` | Create | `judge_endpoint_url`, `instance_name` |
| `infra/gcp/judge/startup.sh.tpl` | Create | Same pattern as L4; extra `--max-model-len 4096 --gpu-memory-utilization 0.95` vLLM flags |
| `infra/gcp/judge/.gitignore` | Create | `*.tfstate`, `.terraform/`, `*.tfvars` |
| `infra/gcp/judge/Makefile` | Create | `judge-up`, `judge-down`, `judge-health`, `judge-ssh` |
| `shared/models/registry/qwen2.5-72b-instruct-awq-vllm-a2.yaml` | Create | Model manifest, `target_host: cloud-burst-a2`, endpoint placeholder |
| `shared/goldsets/schema.py` | Modify | Add `rubric: str \| None`, `reference: str \| None`, optional `value`, `@model_validator` |
| `shared/eval/judges/configs/v0.2.yaml` | Create | Extends v0.1 with `lm_judge` config; registers new bundle |
| `shared/eval/judges/aggregate.py` | Modify | Add optional `rendered_prompt`, `raw_response`, `rationale`, `usage`, `cost_increment_usd`, `wall_ms` to `Judgement` |
| `shared/eval/runner/runner.py` | Modify | `_lm_judge_score` helper; `elif expected.type == "rubric":` routing; extended `_write_judgement_row`; `judge_client_factory` injection param |
| `tests/shared/eval/test_lm_judge.py` | Create | Unit tests: happy path, parse failure, no reference |
| `tests/shared/goldsets/test_schema.py` | Modify | Add rubric Expected validation tests |
| `tests/integration/test_runner.py` | Modify | Add rubric-type example to fixture; assert judgement row populated |

---

### Task 1: Terraform Judge Workspace

**Files:**
- Create: `infra/gcp/judge/main.tf`
- Create: `infra/gcp/judge/variables.tf`
- Create: `infra/gcp/judge/outputs.tf`
- Create: `infra/gcp/judge/startup.sh.tpl`
- Create: `infra/gcp/judge/.gitignore`
- Create: `infra/gcp/judge/Makefile`

**Interfaces:**
- Produces: `judge_endpoint_url` Terraform output (consumed by v0.2 bundle YAML step)
- Produces: startup script that launches vLLM with `--max-model-len 4096 --gpu-memory-utilization 0.95`

- [ ] **Step 1: Create directory**

```bash
mkdir -p infra/gcp/judge
```

- [ ] **Step 2: Write `infra/gcp/judge/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "zone" {
  description = "GCP zone for the judge instance"
  type        = string
  default     = "asia-southeast1-b"
}

variable "judge_model_id" {
  description = "HuggingFace model ID for the judge"
  type        = string
  default     = "Qwen/Qwen2.5-72B-Instruct-AWQ"
}

variable "judge_model_revision" {
  description = "Model revision (git SHA or tag)"
  type        = string
  default     = "main"
}

variable "vllm_version" {
  description = "vLLM Docker image tag"
  type        = string
  default     = "v0.4.3"
}

variable "hf_token" {
  description = "HuggingFace API token (may be needed for gated models)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "preemptible" {
  description = "Use preemptible instance to reduce cost"
  type        = bool
  default     = true
}
```

- [ ] **Step 3: Write `infra/gcp/judge/main.tf`**

```hcl
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  region = regex("^(.+)-[a-z]$", var.zone)[0]
}

provider "google" {
  project = var.project_id
  region  = local.region
}

# ── Reference existing GCS model weight cache ────────────────────────────────

data "google_storage_bucket" "model_cache" {
  name = "${var.project_id}-ai-experiments-model-cache"
}

# ── Static external IP ────────────────────────────────────────────────────────

resource "google_compute_address" "judge_ip" {
  name   = "judge-static-ip"
  region = local.region
}

# ── Firewall: allow judge inference traffic on port 8000 ──────────────────────

resource "google_compute_firewall" "judge_inference" {
  name    = "allow-judge-inference"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["judge-server"]
}

# ── GCE instance ──────────────────────────────────────────────────────────────

resource "google_compute_instance" "judge" {
  name         = "vllm-judge-server"
  machine_type = "a2-highgpu-1g"
  zone         = var.zone

  tags = ["judge-server"]

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/common-dl-gpu-debian-11-py310"
      size  = 200  # GB; 72B AWQ weights (~36 GB) + Docker layers
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.judge_ip.address
    }
  }

  scheduling {
    preemptible         = var.preemptible
    automatic_restart   = !var.preemptible
    on_host_maintenance = "TERMINATE"
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      model_id       = var.judge_model_id
      model_revision = var.judge_model_revision
      bucket_name    = data.google_storage_bucket.model_cache.name
      hf_token       = var.hf_token
      vllm_version   = var.vllm_version
    })
  }

  service_account {
    scopes = [
      "https://www.googleapis.com/auth/devstorage.read_write",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
    ]
  }
}
```

- [ ] **Step 4: Write `infra/gcp/judge/outputs.tf`**

```hcl
output "judge_endpoint_url" {
  value       = "http://${google_compute_address.judge_ip.address}:8000/v1"
  description = "OpenAI-compatible judge endpoint. Copy into shared/eval/judges/configs/v0.2.yaml."
}

output "instance_name" {
  value       = google_compute_instance.judge.name
  description = "GCE instance name (used by make judge-ssh)"
}
```

- [ ] **Step 5: Write `infra/gcp/judge/startup.sh.tpl`**

Identical to `infra/gcp/startup.sh.tpl` except the Docker run command adds `--max-model-len 4096 --gpu-memory-utilization 0.95`:

```bash
#!/bin/bash
# GCE startup script — rendered by Terraform templatefile().
# Runs once at instance boot; logs to GCE serial console.
set -euo pipefail

MODEL_ID="${model_id}"
MODEL_REVISION="${model_revision}"
BUCKET="${bucket_name}"
HF_TOKEN="${hf_token}"
VLLM_VERSION="${vllm_version}"
LOCAL_MODEL_DIR="/model"
SENTINEL="gs://$BUCKET/$MODEL_ID/.cache_complete"

echo "[startup] model_id=$MODEL_ID revision=$MODEL_REVISION bucket=$BUCKET vllm=$VLLM_VERSION"

if [ -n "$HF_TOKEN" ]; then
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

mkdir -p "$LOCAL_MODEL_DIR"

if gsutil -q stat "$SENTINEL" 2>/dev/null; then
  echo "[startup] cache hit — syncing from gs://$BUCKET/$MODEL_ID/"
  gsutil -m rsync -r "gs://$BUCKET/$MODEL_ID/" "$LOCAL_MODEL_DIR/"
else
  echo "[startup] cache miss — pulling from HuggingFace (72B AWQ ~45 min)"
  pip install -q "huggingface_hub[cli]"
  huggingface-cli download "$MODEL_ID" \
    --revision "$MODEL_REVISION" \
    --local-dir "$LOCAL_MODEL_DIR" \
    --local-dir-use-symlinks False
  echo "[startup] seeding GCS cache"
  gsutil -m rsync -r "$LOCAL_MODEL_DIR/" "gs://$BUCKET/$MODEL_ID/"
  echo "complete" | gsutil cp - "$SENTINEL"
fi

echo "[startup] starting vLLM $VLLM_VERSION"
docker run -d \
  --name vllm-server \
  --restart unless-stopped \
  --gpus all \
  -v "$LOCAL_MODEL_DIR:/model" \
  -p 8000:8000 \
  "vllm/vllm-openai:$VLLM_VERSION" \
  --model /model \
  --served-model-name "$MODEL_ID" \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.95

echo "[startup] waiting for vLLM to become ready..."
MAX_WAIT=300
WAITED=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  sleep 5
  WAITED=$((WAITED + 5))
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[startup] ERROR: vLLM did not become ready after ${MAX_WAIT}s — last container logs:"
    docker logs vllm-server 2>&1 | tail -30
    exit 1
  fi
done
echo "[startup] vLLM ready at http://localhost:8000/v1"
```

- [ ] **Step 6: Write `infra/gcp/judge/.gitignore`**

```
*.tfstate
*.tfstate.backup
.terraform/
*.tfvars
```

- [ ] **Step 7: Write `infra/gcp/judge/Makefile`**

```makefile
ZONE ?= asia-southeast1-b

.PHONY: judge-up judge-down judge-health judge-ssh

judge-up:
	terraform apply -auto-approve

judge-down:
	terraform destroy -auto-approve

judge-health:
	@echo "Waiting for judge endpoint to become ready..."
	@until curl -sf "$$(terraform output -raw judge_endpoint_url)/health" >/dev/null; do \
		sleep 5; \
	done
	@echo "Ready: $$(terraform output -raw judge_endpoint_url)"

judge-ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
```

- [ ] **Step 8: Validate**

```bash
cd infra/gcp/judge
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 9: Commit**

```bash
git add infra/gcp/judge/
git commit -m "feat: Terraform workspace for A100 judge (infra/gcp/judge/)"
```

---

### Task 2: Model Manifest

**Files:**
- Create: `shared/models/registry/qwen2.5-72b-instruct-awq-vllm-a2.yaml`

**Interfaces:**
- Consumes: `target_host: cloud-burst-a2` (already in `ModelManifest` Literal and `_TIER1_HOSTS`)
- Produces: Model manifest loaded by `resolve("Qwen/Qwen2.5-72B-Instruct-AWQ")` for smoke tests

- [ ] **Step 1: Write manifest**

```yaml
# A100 cloud-burst judge target.
# endpoint: fill from `cd infra/gcp/judge && terraform output -raw judge_endpoint_url`

id: "Qwen/Qwen2.5-72B-Instruct-AWQ"
family: qwen2.5
size: 72b
revision: "main"
quantization: awq
runtime: vllm
runtime_version: "0.4.3"
target_host: cloud-burst-a2
endpoint: "http://PLACEHOLDER:8000/v1"
capabilities: [chat]
context_window: 4096
default_sampling:
  temperature: 0.0
  top_p: 1.0
  max_tokens: 256
```

- [ ] **Step 2: Commit**

```bash
git add shared/models/registry/qwen2.5-72b-instruct-awq-vllm-a2.yaml
git commit -m "feat: model manifest for qwen2.5-72b-instruct-awq on cloud-burst-a2"
```

---

### Task 3: Expected Schema + v0.2 Bundle

**Files:**
- Modify: `shared/goldsets/schema.py`
- Create: `shared/eval/judges/configs/v0.2.yaml`
- Modify: `tests/shared/goldsets/test_schema.py` (add if absent)

**Interfaces:**
- Produces: `Expected(type="rubric", rubric="...", reference="...")` — used by runner in Task 4
- Produces: `v0.2.yaml` loaded by `register_bundle("v0.2")` — used by integration test in Task 5

- [ ] **Step 1: Write failing schema tests**

File: `tests/shared/goldsets/test_schema.py` (create or add to existing)

```python
import pytest
from pydantic import ValidationError
from shared.goldsets.schema import Expected


def test_exact_requires_value():
    e = Expected(type="exact", value="Paris")
    assert e.value == "Paris"
    assert e.rubric is None


def test_exact_raises_without_value():
    with pytest.raises(ValidationError, match="value is required"):
        Expected(type="exact", value=None)


def test_set_requires_value():
    e = Expected(type="set", value=["Paris", "Lyon"])
    assert e.value == ["Paris", "Lyon"]


def test_rubric_requires_rubric_field():
    with pytest.raises(ValidationError, match="rubric is required"):
        Expected(type="rubric")


def test_rubric_valid_with_no_reference():
    e = Expected(type="rubric", rubric="Award 1.0 if correct.")
    assert e.rubric == "Award 1.0 if correct."
    assert e.reference is None
    assert e.value is None


def test_rubric_valid_with_reference():
    e = Expected(type="rubric", rubric="Award 1.0 if correct.", reference="Singapore")
    assert e.reference == "Singapore"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/shared/goldsets/test_schema.py -v
```

Expected: failures on rubric-related tests (fields don't exist yet).

- [ ] **Step 3: Update `shared/goldsets/schema.py`**

```python
"""Per-example JSONL record schema (spec §3)."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_LANES = {"general", "sea", "japanese", "ocr", "finance"}
ALLOWED_EXPECTED_TYPES = {"exact", "set", "rubric"}
EXAMPLE_ID_RE = re.compile(r"^ex_[a-z]+_[a-z0-9]+$")


class Expected(BaseModel):
    type: Literal["exact", "set", "rubric"]
    value: Any | None = None
    rubric: str | None = None
    reference: str | None = None

    @model_validator(mode="after")
    def _check_type_fields(self) -> "Expected":
        if self.type in {"exact", "set"}:
            if self.value is None:
                raise ValueError(f"expected.value is required for type={self.type!r}")
        elif self.type == "rubric":
            if self.rubric is None:
                raise ValueError("expected.rubric is required for type='rubric'")
        return self


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

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/shared/goldsets/test_schema.py -v
```

Expected: all PASS.

- [ ] **Step 5: Write `shared/eval/judges/configs/v0.2.yaml`**

```yaml
# Sprint 2 judge bundle: adds lm_judge for rubric-type examples.
# endpoint: fill from `cd infra/gcp/judge && terraform output -raw judge_endpoint_url`
# then re-run: uv run python -c "from shared.eval.judges import register_bundle; register_bundle('v0.2')"

version: v0.2
routing:
  by_expected_type:
    exact:  [deterministic]
    set:    [deterministic]
    rubric: [lm_judge]
  by_lane_override: {}
judges:
  deterministic:
    config:
      string_normalize: [lowercase, strip_punct, whitespace_collapse]
      numeric_tolerance_abs: 1.0e-6
      numeric_tolerance_rel: 1.0e-3
  lm_judge:
    model_id: "Qwen/Qwen2.5-72B-Instruct-AWQ"
    endpoint: "http://PLACEHOLDER:8000/v1"
    rubric_template: |
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
    max_tokens: 128
    temperature: 0.0
aggregation:
  rule: weighted_mean
  tie_break: deterministic
  weights:
    deterministic: 1.0
    lm_judge: 1.0
calibration:
  human_calibration_set: null
  kappa_threshold: 0.80
  per_task_kappa: {}
trust:
  enforcement: lenient
rubrics: {}
notes: |
  Sprint 2 bundle. Deterministic for exact/set; lm_judge for rubric.
  Qwen2.5-72B-Instruct-AWQ on cloud-burst-a2 (A100 40 GB).
  Update lm_judge.endpoint from terraform output before running campaigns.
```

- [ ] **Step 6: Verify YAML loads cleanly**

```bash
uv run python -c "
import yaml; from pathlib import Path
b = yaml.safe_load(Path('shared/eval/judges/configs/v0.2.yaml').read_text())
assert b['version'] == 'v0.2'
assert 'lm_judge' in b['judges']
assert '{{ question }}' in b['judges']['lm_judge']['rubric_template']
print('ok')
"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add shared/goldsets/schema.py \
        tests/shared/goldsets/test_schema.py \
        shared/eval/judges/configs/v0.2.yaml
git commit -m "feat: Expected rubric/reference fields + v0.2 judge bundle"
```

---

### Task 4: LM Judge Routing

**Files:**
- Modify: `shared/eval/judges/aggregate.py` — extend `Judgement` with optional lm_judge fields
- Modify: `shared/eval/runner/runner.py` — `_lm_judge_score` helper; extended `_write_judgement_row`; rubric routing; `judge_client_factory` injection
- Create: `tests/shared/eval/test_lm_judge.py` — unit tests for `_lm_judge_score` (written first, TDD)

**Interfaces:**
- Consumes: `Expected.rubric`, `Expected.reference` from Task 3
- Consumes: `bundle["judges"]["lm_judge"]` from v0.2 YAML (Task 3)
- Produces: `_lm_judge_score(rendered_eval_prompt, response_text, expected, bundle, *, judge_client_factory=None) -> Judgement`
- Produces: `run_campaign(..., judge_client_factory=None)` — new injection param

- [ ] **Step 1: Confirm Jinja2 is available**

```bash
uv run python -c "import jinja2; print(jinja2.__version__)"
```

If this fails, add it: `uv add jinja2`

- [ ] **Step 2: Write failing unit tests**

Create `tests/shared/eval/test_lm_judge.py`:

```python
"""Unit tests for _lm_judge_score helper."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from shared.eval.runner.runner import _lm_judge_score
from shared.goldsets.schema import Expected

_RUBRIC_TEMPLATE = """\
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
"""

_BUNDLE = {
    "judges": {
        "lm_judge": {
            "model_id": "Qwen/Qwen2.5-72B-Instruct-AWQ",
            "endpoint": "http://127.0.0.1:8000/v1",
            "rubric_template": _RUBRIC_TEMPLATE,
            "max_tokens": 128,
            "temperature": 0.0,
        }
    },
    "aggregation": {"weights": {"lm_judge": 1.0}},
    "trust": {"enforcement": "lenient"},
}


def _make_resp(content: str, prompt_tokens: int = 50, completion_tokens: int = 20) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    return resp


def _mock_judge_factory(resp: MagicMock):
    def factory(cfg):  # noqa: ARG001
        client = MagicMock()
        client.chat.return_value = resp
        return client
    return factory


def test_happy_path_with_reference():
    expected = Expected(type="rubric", rubric="Award 1.0 if correct.", reference="Singapore")
    resp = _make_resp("SCORE: 0.9\nRATIONALE: The answer correctly identifies Singapore.")

    result = _lm_judge_score(
        "What is the richest SEA country?", "Singapore", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.judge_role == "lm_judge"
    assert result.score == pytest.approx(0.9)
    assert result.parse_error is False
    assert result.rationale == "The answer correctly identifies Singapore."
    assert result.raw_response is not None
    assert result.rendered_prompt is not None
    assert "Singapore" in result.rendered_prompt  # reference rendered into prompt


def test_parse_failure_returns_parse_error():
    expected = Expected(type="rubric", rubric="Award 1.0 if correct.")
    resp = _make_resp("I think the answer is pretty good overall.")  # no SCORE: line

    result = _lm_judge_score(
        "Q", "A", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.parse_error is True
    assert result.score is None
    assert result.judge_role == "lm_judge"


def test_no_reference_field_renders_cleanly():
    expected = Expected(type="rubric", rubric="Award 1.0 if the answer mentions GDP.")
    resp = _make_resp("SCORE: 0.5\nRATIONALE: Partial answer.")

    result = _lm_judge_score(
        "Q", "A", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.score == pytest.approx(0.5)
    assert result.parse_error is False
    assert result.rendered_prompt is not None
    assert "Reference answer" not in result.rendered_prompt  # no reference block


def test_score_clamped_to_unit_interval():
    expected = Expected(type="rubric", rubric="Score between 0 and 1.")
    resp = _make_resp("SCORE: 1.5\nRATIONALE: Exceeded rubric ceiling.")

    result = _lm_judge_score(
        "Q", "A", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.score == pytest.approx(1.0)  # clamped
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
uv run pytest tests/shared/eval/test_lm_judge.py -v
```

Expected: `ImportError` or `AttributeError` since `_lm_judge_score` doesn't exist yet.

- [ ] **Step 4: Extend `Judgement` dataclass in `shared/eval/judges/aggregate.py`**

```python
"""Aggregation rule (spec §4): deterministic tie-break, else weighted mean."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Judgement:
    judge_role: str
    score: float | None
    score_kind: str
    parse_error: bool = False
    rendered_prompt: str | None = None
    raw_response: str | None = None
    rationale: str | None = None
    usage: dict | None = None
    cost_increment_usd: float = 0.0
    wall_ms: int | None = None


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
    kinds = {j.score_kind for j in usable}
    kind_out = kinds.pop() if len(kinds) == 1 else "rubric_aggregate"
    return num / den, kind_out
```

Note: add `field` to the dataclass imports (`from dataclasses import dataclass, field`) even if unused — it removes the need to re-import when future fields need defaults. Actually just add it in case; it's a standard import.

Wait, `field` is not used here. Let me not add it gratuitously — YAGNI. Keep the import as `from dataclasses import dataclass`.

- [ ] **Step 5: Add `_lm_judge_score` helper and routing to `shared/eval/runner/runner.py`**

**5a.** Add these imports at the top (after existing imports):

```python
import re

from jinja2 import Template
```

Also add `_JUDGE_HOST` and the compiled regexes near the top of the module (before any function definitions):

```python
_JUDGE_HOST = "cloud-burst-a2"
_SCORE_RE = re.compile(r"SCORE:\s*([\d.]+)")
_RATIONALE_RE = re.compile(r"RATIONALE:\s*(.+)")
```

**5b.** Add `judge_client_factory=None` to `run_campaign` signature:

```python
def run_campaign(
    model_id: str,
    gold_set_version: str,
    judge_config_version: str,
    max_cost_usd: float,
    template_root: Path,
    experiment_id: str | None = None,
    test: bool = False,
    teardown_hook: TeardownHook | None = None,
    inference_client_factory=None,
    judge_client_factory=None,  # for test injection only
) -> RunResult:
```

**5c.** Replace the `else:` block in the scoring loop (lines 194–197 in the original) with:

```python
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
                elif expected.type == "rubric":
                    if "lm_judge" not in bundle.get("judges", {}):
                        error_class = "judge_parse_failed"
                        error_body = {"reason": "lm_judge not configured in bundle"}
                    else:
                        judgement_row = _lm_judge_score(
                            rendered, response_text, expected, bundle,
                            judge_client_factory=judge_client_factory,
                        )
                        if judgement_row.parse_error:
                            error_class = "judge_parse_failed"
                            error_body = {
                                "reason": "lm_judge parse failed",
                                "raw_response": judgement_row.raw_response,
                            }
                        else:
                            agg_score, agg_kind = aggregate(
                                [judgement_row], bundle["aggregation"]["weights"]
                            )
                else:
                    error_class = "judge_parse_failed"
                    error_body = {"reason": f"unknown expected.type={expected.type!r}"}
```

**5d.** Update `_write_judgement_row` to write all judgement columns:

```python
def _write_judgement_row(*, result_id, judgement: Judgement, bundle, test=False):
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO judgement (
                id, result_id, judge_role, judge_manifest,
                rendered_prompt, raw_response, score, score_kind,
                rationale, parse_error, usage, cost_increment_usd, wall_ms
            ) VALUES (
                %s, %s, %s, %s::jsonb,
                %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s, %s
            )
            """,
            (
                uuid.uuid4(), result_id, judgement.judge_role,
                json.dumps(bundle["judges"].get(judgement.judge_role, {})),
                judgement.rendered_prompt, judgement.raw_response,
                judgement.score, judgement.score_kind,
                judgement.rationale, judgement.parse_error,
                json.dumps(judgement.usage) if judgement.usage else None,
                judgement.cost_increment_usd, judgement.wall_ms,
            ),
        )
```

**5e.** Add `_lm_judge_score` helper at the bottom of the helpers section (after `_default_client_factory`):

```python
def _lm_judge_score(
    rendered_eval_prompt: str,
    response_text: str,
    expected: Expected,
    bundle: dict,
    *,
    judge_client_factory=None,
) -> Judgement:
    lm_cfg = bundle["judges"]["lm_judge"]
    judge_rendered = Template(lm_cfg["rubric_template"]).render(
        question=rendered_eval_prompt,
        response=response_text,
        rubric=expected.rubric,
        reference=expected.reference,
    )

    call_started = time.time()

    if judge_client_factory is not None:
        judge_client = judge_client_factory(lm_cfg)
    else:
        judge_client = InferenceClient(
            endpoint=lm_cfg["endpoint"],
            model=lm_cfg["model_id"],
            timeout_s=120.0,
        )

    try:
        resp = judge_client.chat(ChatRequest(
            messages=[Message(role="user", content=judge_rendered)],
            temperature=lm_cfg.get("temperature", 0.0),
            max_tokens=lm_cfg.get("max_tokens", 128),
        ))
        raw_response = resp.content
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
        }
    except InferenceError as e:
        raw_response = f"[judge_error: {e}]"
        usage = None

    wall_ms = int((time.time() - call_started) * 1000)
    judge_accountant = CostAccountant.for_target(_JUDGE_HOST)
    cost_inc = judge_accountant.cost_per_call(
        usage["prompt_tokens"] if usage else None,
        usage["completion_tokens"] if usage else None,
        wall_ms,
    )

    match = _SCORE_RE.search(raw_response)
    if match:
        score = max(0.0, min(1.0, float(match.group(1))))
        rationale_match = _RATIONALE_RE.search(raw_response)
        rationale = rationale_match.group(1).strip() if rationale_match else None
        parse_error = False
    else:
        score = None
        rationale = None
        parse_error = True

    return Judgement(
        judge_role="lm_judge",
        score=score,
        score_kind="scalar",
        parse_error=parse_error,
        rendered_prompt=judge_rendered,
        raw_response=raw_response,
        rationale=rationale,
        usage=usage,
        cost_increment_usd=cost_inc,
        wall_ms=wall_ms,
    )
```

- [ ] **Step 6: Run unit tests**

```bash
uv run pytest tests/shared/eval/test_lm_judge.py -v
```

Expected: all 4 PASS.

- [ ] **Step 7: Run full unit test suite to check for regressions**

```bash
uv run pytest tests/shared/ -v --ignore=tests/shared/eval/test_lm_judge.py
```

Expected: all PASS (especially `test_preflight.py` — confirm the `Judgement` dataclass change didn't break the aggregate).

- [ ] **Step 8: Commit**

```bash
git add shared/eval/judges/aggregate.py \
        shared/eval/runner/runner.py \
        tests/shared/eval/test_lm_judge.py
git commit -m "feat: _lm_judge_score helper + rubric routing in runner"
```

---

### Task 5: Integration Test Update

**Files:**
- Modify: `tests/integration/test_runner.py`

**Interfaces:**
- Consumes: `run_campaign(..., judge_client_factory=...)` from Task 4
- Consumes: `Expected(type="rubric", rubric=..., reference=...)` from Task 3
- Consumes: `register_bundle("v0.2", test=True)` to seed v0.2 bundle into test DB

**Note:** Read the existing `tests/integration/test_runner.py` before making changes. Follow its existing fixture structure — DB setup, gold set seeding, example count, `run_campaign` call pattern. The rubric example joins the existing test gold set.

- [ ] **Step 1: Read the existing integration test**

```bash
cat tests/integration/test_runner.py
```

Understand: how examples are seeded, what judge config version is used, how `inference_client_factory` is injected.

- [ ] **Step 2: Add a rubric example to the test fixture**

In the existing gold set seeding block, add one rubric example alongside the existing exact/set examples:

```python
# Rubric-type example
cur.execute(
    "INSERT INTO gold_example (example_id, version, lane, prompt_template, inputs, expected, never_to_third_party) "
    "VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)",
    (
        "ex_general_rubric01",
        TEST_GOLD_VERSION,
        "general",
        "qa",
        json.dumps({"question": "What is the richest country in SEA by GDP per capita?"}),
        json.dumps({
            "type": "rubric",
            "rubric": "Award 1.0 if the answer correctly identifies Singapore. Award 0.5 if only partially correct. Award 0.0 otherwise.",
            "reference": "Singapore",
        }),
        False,
    ),
)
```

- [ ] **Step 3: Seed v0.2 bundle into the test DB**

In the fixture setup block (after `register_bundle("v0.1", test=True)`), add:

```python
register_bundle("v0.2", test=True)
```

- [ ] **Step 4: Build a mock judge factory**

Add this helper near the top of the test file:

```python
def _mock_judge_factory_for(score: float, rationale: str = "Test rationale."):
    """Returns a judge_client_factory that always returns a fixed SCORE."""
    from unittest.mock import MagicMock

    def factory(cfg):  # noqa: ARG001
        client = MagicMock()
        resp = MagicMock()
        resp.content = f"SCORE: {score}\nRATIONALE: {rationale}"
        resp.usage.prompt_tokens = 40
        resp.usage.completion_tokens = 15
        client.chat.return_value = resp
        return client

    return factory
```

- [ ] **Step 5: Add rubric-route assertion to the integration test**

Add a new test (or extend the existing `test_run_campaign_*` test) that runs with the v0.2 bundle and checks the rubric example's judgement row:

```python
def test_run_campaign_rubric_example(db_fixture):  # adjust fixture name to match existing
    """Rubric example routes through lm_judge; judgement row has score and raw_response."""
    result = run_campaign(
        model_id=TEST_MODEL_ID,
        gold_set_version=TEST_GOLD_VERSION,
        judge_config_version="v0.2",
        max_cost_usd=10.0,
        template_root=TEMPLATE_ROOT,
        test=True,
        inference_client_factory=_mock_inference_factory(),   # use existing mock
        judge_client_factory=_mock_judge_factory_for(0.8),
    )

    assert result.status == "completed"

    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT j.score, j.raw_response, j.judge_role "
            "FROM judgement j "
            "JOIN result r ON r.id = j.result_id "
            "WHERE r.example_id = 'ex_general_rubric01' AND r.run_id = %s",
            (result.run_id,),
        )
        row = cur.fetchone()

    assert row is not None, "no judgement row for rubric example"
    score, raw_response, judge_role = row
    assert float(score) == pytest.approx(0.8)
    assert raw_response is not None
    assert "SCORE: 0.8" in raw_response
    assert judge_role == "lm_judge"
```

- [ ] **Step 6: Run integration test**

```bash
uv run pytest tests/integration/test_runner.py -v
```

Expected: all tests PASS including the new rubric test.

- [ ] **Step 7: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add tests/integration/test_runner.py
git commit -m "test: rubric-route integration test with mock lm_judge"
```

---

## Self-Review

**Spec coverage check:**

| Spec Requirement | Task |
|---|---|
| `infra/gcp/judge/` Terraform workspace (a2-highgpu-1g, firewall 8000, static IP, GCS data source) | Task 1 |
| `judge/startup.sh.tpl` with `--max-model-len 4096 --gpu-memory-utilization 0.95` | Task 1 |
| `judge/Makefile` with `judge-up/down/health/ssh` | Task 1 |
| Model manifest `qwen2.5-72b-instruct-awq-vllm-a2.yaml` | Task 2 |
| `Expected.rubric`, `Expected.reference` fields + validator | Task 3 |
| v0.2 bundle YAML with `lm_judge` config + Jinja2 rubric template | Task 3 |
| `_lm_judge_score` — renders Jinja2, calls InferenceClient, parses SCORE regex | Task 4 |
| Rubric routing in `run_campaign` | Task 4 |
| `_write_judgement_row` writes `rendered_prompt`, `raw_response`, `rationale`, `usage`, `cost_increment_usd`, `wall_ms` | Task 4 |
| Judge cost in `judgement.cost_increment_usd` only (not campaign budget) | Task 4 |
| `judge_client_factory` injection for tests | Task 4 |
| Unit tests: happy path, parse failure, no reference, score clamping | Task 4 |
| Integration test: rubric example, judgement row populated | Task 5 |
| v0.1 bundle unchanged (rubric path guarded by `"lm_judge" not in bundle["judges"]`) | Task 4 |
| `cloud-burst-a2` already in `_TIER1_HOSTS` — no guardrail change | No task (confirmed in-spec) |

**Gaps fixed during review:**
- Added score clamping test (`test_score_clamped_to_unit_interval`) — spec says clamp to [0,1]
- Added `_mock_judge_factory_for` helper note in Task 5 Step 4 — can't leave it implicit
- Noted that `register_bundle("v0.2", test=True)` must be called in fixture setup before the rubric-route test (Step 3 added explicitly)
