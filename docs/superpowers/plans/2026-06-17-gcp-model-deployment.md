# GCP Model Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the GCP cloud-burst deployment target into the eval substrate — Terraform provisions a GCE L4 GPU instance running vLLM with a GCS model cache; new manifest/rate-card YAMLs let the existing runner point campaigns at the endpoint with no runner code changes.

**Architecture:** Terraform in `infra/gcp/` manages four GCP resources (static IP, GCS bucket, firewall, GCE instance); a startup-script template installs vLLM via Docker and populates a model weight cache in GCS; new `target_host` Literal values and YAML files wire the target into the existing manifest/cost-accountant machinery.

**Tech Stack:** Terraform ~> 5.0 (hashicorp/google provider), GCE Deep Learning VM image (CUDA + Docker pre-installed), vLLM Docker image (`vllm/vllm-openai`), GCS, Python/Pydantic (manifest schema), pytest.

> **Spec note:** `RateCard.unit` is `Literal["per_mtok"]` — only one value supported in v0.1. The design spec incorrectly wrote `unit: per_hour`; the correct value is `per_mtok`, consistent with `mac.yaml`. All rate cards in this plan use `per_mtok`.

---

## File map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `shared/models/manifest.py` | Add `cloud-burst-l4`, `cloud-burst-a2` to `target_host` Literal |
| Modify | `tests/shared/models/test_manifest.py` | Tests for new target_host values |
| Create | `shared/eval/cost/rate_cards/cloud-burst-l4.yaml` | L4 spot rate card (~$0.70/hr) |
| Create | `shared/eval/cost/rate_cards/cloud-burst-a2.yaml` | A100 spot rate card (~$2.50/hr) |
| Modify | `tests/shared/eval/test_cost.py` | Tests for new rate cards |
| Create | `infra/gcp/variables.tf` | Terraform input variables |
| Create | `infra/gcp/outputs.tf` | Terraform outputs (endpoint_url, instance_name, bucket_name) |
| Create | `infra/gcp/main.tf` | GCP resources (bucket, static IP, firewall, instance) |
| Create | `infra/gcp/startup.sh.tpl` | VM startup script template (GCS cache + vLLM) |
| Create | `infra/gcp/Makefile` | `make up / down / health / ssh` |
| Create | `infra/gcp/.gitignore` | Exclude tfstate, .terraform/, *.tfvars |
| Create | `infra/gcp/terraform.tfvars.example` | Example variable values |
| Create | `shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml` | L4 model manifest (endpoint filled after apply) |

---

## Task 1: Extend manifest.py target_host Literal

**Files:**
- Modify: `shared/models/manifest.py`
- Modify: `tests/shared/models/test_manifest.py`

- [ ] **Step 1: Write failing tests for cloud-burst-l4 and cloud-burst-a2**

Add to `tests/shared/models/test_manifest.py`:

```python
def test_cloud_burst_l4_target_host_accepted(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: qwen2.5-7b-instruct-vllm-l4
        family: qwen2.5
        size: 7b
        revision: "2024-09-19"
        runtime: vllm
        runtime_version: "0.4.3"
        target_host: cloud-burst-l4
        endpoint: "http://1.2.3.4:8000/v1"
        capabilities: [chat]
        context_window: 131072
        default_sampling:
            temperature: 0.0
            top_p: 1.0
            max_tokens: 256
    """))
    m = load_manifest_yaml(yaml_path)
    assert m.target_host == "cloud-burst-l4"


def test_cloud_burst_a2_target_host_accepted(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: qwen2.5-14b-instruct-vllm-a2
        family: qwen2.5
        size: 14b
        revision: "2024-09-19"
        runtime: vllm
        runtime_version: "0.4.3"
        target_host: cloud-burst-a2
        endpoint: "http://1.2.3.4:8000/v1"
        capabilities: [chat]
        context_window: 131072
        default_sampling:
            temperature: 0.0
            top_p: 1.0
            max_tokens: 256
    """))
    m = load_manifest_yaml(yaml_path)
    assert m.target_host == "cloud-burst-a2"


def test_unknown_target_host_rejected(tmp_path: Path) -> None:
    yaml_path = tmp_path / "m.yaml"
    yaml_path.write_text(textwrap.dedent("""\
        id: x
        family: x
        size: x
        revision: "x"
        runtime: ollama
        runtime_version: x
        target_host: cloud-burst-z99
        endpoint: x
        capabilities: []
        context_window: 1
        default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 1}
    """))
    with pytest.raises(ValueError):
        load_manifest_yaml(yaml_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/huiliang/GitHub/ai-experiments
python -m pytest tests/shared/models/test_manifest.py::test_cloud_burst_l4_target_host_accepted tests/shared/models/test_manifest.py::test_cloud_burst_a2_target_host_accepted -v
```

Expected: FAIL — `cloud-burst-l4` and `cloud-burst-a2` not in Literal.

- [ ] **Step 3: Add new target_host values to manifest.py**

In `shared/models/manifest.py`, change line:
```python
    target_host: Literal["mac", "spark", "cloud-burst-a3", "cloud-burst-p5"]
```
to:
```python
    target_host: Literal["mac", "spark", "cloud-burst-l4", "cloud-burst-a2", "cloud-burst-a3", "cloud-burst-p5"]
```

- [ ] **Step 4: Run all manifest tests**

```bash
python -m pytest tests/shared/models/test_manifest.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/models/manifest.py tests/shared/models/test_manifest.py
git commit -m "feat: add cloud-burst-l4 and cloud-burst-a2 target_host values"
```

---

## Task 2: Add cloud-burst rate card YAMLs

**Files:**
- Create: `shared/eval/cost/rate_cards/cloud-burst-l4.yaml`
- Create: `shared/eval/cost/rate_cards/cloud-burst-a2.yaml`
- Modify: `tests/shared/eval/test_cost.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/shared/eval/test_cost.py`:

```python
def test_load_rate_card_for_cloud_burst_l4() -> None:
    rc = load_rate_card("cloud-burst-l4")
    assert rc.target_host == "cloud-burst-l4"
    assert rc.unit == "per_mtok"
    assert rc.wall_usd_per_hour == pytest.approx(0.70)
    assert rc.prompt_usd_per_mtok == 0.0
    assert rc.completion_usd_per_mtok == 0.0


def test_load_rate_card_for_cloud_burst_a2() -> None:
    rc = load_rate_card("cloud-burst-a2")
    assert rc.target_host == "cloud-burst-a2"
    assert rc.unit == "per_mtok"
    assert rc.wall_usd_per_hour == pytest.approx(2.50)
    assert rc.prompt_usd_per_mtok == 0.0
    assert rc.completion_usd_per_mtok == 0.0


def test_cloud_burst_l4_wall_cost() -> None:
    rc = load_rate_card("cloud-burst-l4")
    # 1 hour at $0.70/hr
    cost = CostAccountant.from_rate_card(rc).cost_per_call(
        prompt_tokens=None, completion_tokens=None, wall_ms=3_600_000
    )
    assert cost == pytest.approx(0.70, rel=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/shared/eval/test_cost.py::test_load_rate_card_for_cloud_burst_l4 tests/shared/eval/test_cost.py::test_load_rate_card_for_cloud_burst_a2 -v
```

Expected: FAIL — FileNotFoundError (YAML files don't exist yet).

- [ ] **Step 3: Create cloud-burst-l4.yaml**

Create `shared/eval/cost/rate_cards/cloud-burst-l4.yaml`:

```yaml
# GCE g2-standard-8 (1× L4 24 GB VRAM), preemptible, asia-southeast1.
# Token costs are zero (self-hosted vLLM); only wall-time is billed.
# Rate ~$0.70/hr spot as of 2026-06. Revise quarterly.
target_host: cloud-burst-l4
unit: per_mtok
prompt_usd_per_mtok: 0.0
completion_usd_per_mtok: 0.0
wall_usd_per_hour: 0.70
```

- [ ] **Step 4: Create cloud-burst-a2.yaml**

Create `shared/eval/cost/rate_cards/cloud-burst-a2.yaml`:

```yaml
# GCE a2-highgpu-1g (1× A100 40 GB VRAM), preemptible, asia-southeast1.
# Token costs are zero (self-hosted vLLM); only wall-time is billed.
# Rate ~$2.50/hr spot as of 2026-06. Revise quarterly.
target_host: cloud-burst-a2
unit: per_mtok
prompt_usd_per_mtok: 0.0
completion_usd_per_mtok: 0.0
wall_usd_per_hour: 2.50
```

- [ ] **Step 5: Run all cost tests**

```bash
python -m pytest tests/shared/eval/test_cost.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add shared/eval/cost/rate_cards/cloud-burst-l4.yaml shared/eval/cost/rate_cards/cloud-burst-a2.yaml tests/shared/eval/test_cost.py
git commit -m "feat: add L4 and A100 rate cards for cloud-burst targets"
```

---

## Task 3: Terraform skeleton (variables, outputs, .gitignore, example tfvars)

**Files:**
- Create: `infra/gcp/variables.tf`
- Create: `infra/gcp/outputs.tf`
- Create: `infra/gcp/.gitignore`
- Create: `infra/gcp/terraform.tfvars.example`

- [ ] **Step 1: Create infra/gcp/ directory and .gitignore**

```bash
mkdir -p infra/gcp
```

Create `infra/gcp/.gitignore`:

```
*.tfstate
*.tfstate.backup
.terraform/
*.tfvars
```

Note: `.terraform.lock.hcl` is intentionally NOT gitignored — commit it so provider versions are pinned.

- [ ] **Step 2: Write variables.tf**

Create `infra/gcp/variables.tf`:

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "zone" {
  description = "GCP zone for the GCE instance"
  type        = string
  default     = "asia-southeast1-b"
}

variable "instance_type" {
  description = "GCE machine type. Use g2-standard-8 for L4, a2-highgpu-1g for A100."
  type        = string
  default     = "g2-standard-8"
}

variable "model_id" {
  description = "HuggingFace model ID to serve (e.g. Qwen/Qwen2.5-7B-Instruct)"
  type        = string
  default     = "Qwen/Qwen2.5-7B-Instruct"
}

variable "vllm_version" {
  description = "vLLM Docker image tag (pinned for reproducibility)"
  type        = string
  default     = "v0.4.3"
}

variable "hf_token" {
  description = "HuggingFace API token (required for gated models; leave empty for public models)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "preemptible" {
  description = "Use a preemptible (spot) instance to reduce cost"
  type        = bool
  default     = true
}
```

- [ ] **Step 3: Write outputs.tf**

Create `infra/gcp/outputs.tf`:

```hcl
output "endpoint_url" {
  value       = "http://${google_compute_address.vllm_ip.address}:8000/v1"
  description = "OpenAI-compatible inference endpoint. Copy into the model manifest YAML."
}

output "instance_name" {
  value       = google_compute_instance.vllm.name
  description = "GCE instance name (used by make ssh)"
}

output "bucket_name" {
  value       = google_storage_bucket.model_cache.name
  description = "GCS bucket holding cached model weights"
}
```

- [ ] **Step 4: Write terraform.tfvars.example**

Create `infra/gcp/terraform.tfvars.example`:

```hcl
project_id    = "your-gcp-project-id"
zone          = "asia-southeast1-b"
instance_type = "g2-standard-8"      # L4 24 GB — upgrade to a2-highgpu-1g for A100
model_id      = "Qwen/Qwen2.5-7B-Instruct"
vllm_version  = "v0.4.3"
hf_token      = ""                    # leave empty if model is not gated
preemptible   = true
```

- [ ] **Step 5: Commit**

```bash
git add infra/gcp/.gitignore infra/gcp/variables.tf infra/gcp/outputs.tf infra/gcp/terraform.tfvars.example
git commit -m "feat: terraform skeleton for GCP cloud-burst target (variables, outputs, gitignore)"
```

---

## Task 4: Terraform main.tf (GCP resources)

**Files:**
- Create: `infra/gcp/main.tf`

- [ ] **Step 1: Write main.tf**

Create `infra/gcp/main.tf`:

```hcl
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = "asia-southeast1"
}

# ── GCS model weight cache ──────────────────────────────────────────────────

resource "google_storage_bucket" "model_cache" {
  name                        = "${var.project_id}-ai-experiments-model-cache"
  location                    = "ASIA-SOUTHEAST1"
  uniform_bucket_level_access = true

  lifecycle {
    prevent_destroy = true
  }
}

# ── Static external IP (stable across stop/start) ───────────────────────────

resource "google_compute_address" "vllm_ip" {
  name   = "vllm-static-ip"
  region = "asia-southeast1"
}

# ── Firewall: allow inference traffic on port 8000 ──────────────────────────

resource "google_compute_firewall" "vllm_inference" {
  name    = "allow-vllm-inference"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["vllm-server"]
}

# ── GCE instance ─────────────────────────────────────────────────────────────

resource "google_compute_instance" "vllm" {
  name         = "vllm-eval-server"
  machine_type = var.instance_type
  zone         = var.zone

  tags = ["vllm-server"]

  boot_disk {
    initialize_params {
      # Deep Learning VM: CUDA drivers + Docker pre-installed.
      image = "deeplearning-platform-release/common-dl-gpu-debian-11-py310"
      size  = 100  # GB; model weights + Docker layers
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.vllm_ip.address
    }
  }

  scheduling {
    preemptible         = var.preemptible
    automatic_restart   = !var.preemptible
    on_host_maintenance = "TERMINATE"  # required for GPU instances
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      model_id     = var.model_id
      bucket_name  = google_storage_bucket.model_cache.name
      hf_token     = var.hf_token
      vllm_version = var.vllm_version
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

- [ ] **Step 2: Run terraform init and validate**

```bash
cd infra/gcp
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — fill in your real project_id
terraform init
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 3: Commit**

```bash
cd /Users/huiliang/GitHub/ai-experiments
git add infra/gcp/main.tf infra/gcp/.terraform.lock.hcl
git commit -m "feat: terraform main.tf — GCE L4 instance, GCS bucket, static IP, firewall"
```

---

## Task 5: Startup script template

**Files:**
- Create: `infra/gcp/startup.sh.tpl`

- [ ] **Step 1: Write startup.sh.tpl**

Create `infra/gcp/startup.sh.tpl`:

```bash
#!/bin/bash
# GCE startup script — rendered by Terraform templatefile().
# Runs once at instance boot; logs to GCE serial console.
set -euo pipefail

MODEL_ID="${model_id}"
BUCKET="${bucket_name}"
HF_TOKEN="${hf_token}"
VLLM_VERSION="${vllm_version}"
LOCAL_MODEL_DIR="/model"

echo "[startup] model_id=$MODEL_ID bucket=$BUCKET vllm=$VLLM_VERSION"

# Set HuggingFace token if provided (needed for gated models)
if [ -n "$HF_TOKEN" ]; then
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

mkdir -p "$LOCAL_MODEL_DIR"

# Check GCS cache — copy weights locally if present, else pull from HuggingFace
MODEL_GCS_PATH="gs://$BUCKET/$MODEL_ID"
if gsutil ls "$MODEL_GCS_PATH/" 2>/dev/null | grep -q .; then
  echo "[startup] cache hit — copying from $MODEL_GCS_PATH"
  gsutil -m cp -r "$MODEL_GCS_PATH/*" "$LOCAL_MODEL_DIR/"
else
  echo "[startup] cache miss — pulling from HuggingFace (this takes ~10 min for a 7B model)"
  pip install -q huggingface_hub
  python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('$MODEL_ID', local_dir='$LOCAL_MODEL_DIR')
"
  echo "[startup] seeding GCS cache at $MODEL_GCS_PATH"
  gsutil -m cp -r "$LOCAL_MODEL_DIR/" "$MODEL_GCS_PATH/"
fi

# Start vLLM (Docker is pre-installed on the Deep Learning VM image)
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
  --port 8000

# Health-gate: poll until vLLM is ready (appears in serial console output)
echo "[startup] waiting for vLLM to become ready..."
until curl -sf http://localhost:8000/health; do
  sleep 5
done
echo "[startup] vLLM ready at http://localhost:8000/v1"
```

- [ ] **Step 2: Commit**

```bash
git add infra/gcp/startup.sh.tpl
git commit -m "feat: vLLM startup script template with GCS model cache"
```

---

## Task 6: Makefile

**Files:**
- Create: `infra/gcp/Makefile`

- [ ] **Step 1: Write Makefile**

Create `infra/gcp/Makefile`:

```makefile
ZONE ?= asia-southeast1-b

.PHONY: up down health ssh

up:
	terraform apply -auto-approve

down:
	terraform destroy -auto-approve

health:
	@echo "Waiting for vLLM endpoint to become ready..."
	@until curl -sf "$$(terraform output -raw endpoint_url)/health" >/dev/null; do \
		sleep 5; \
	done
	@echo "Ready: $$(terraform output -raw endpoint_url)"

ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
```

- [ ] **Step 2: Verify make targets parse correctly**

```bash
cd infra/gcp
make --dry-run up
make --dry-run down
```

Expected: prints the terraform commands without running them.

- [ ] **Step 3: Commit**

```bash
cd /Users/huiliang/GitHub/ai-experiments
git add infra/gcp/Makefile
git commit -m "feat: Makefile with up/down/health/ssh targets for GCP eval server"
```

---

## Task 7: Model manifest YAML (L4 target)

**Files:**
- Create: `shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml`

- [ ] **Step 1: Create manifest with placeholder endpoint**

Create `shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml`:

```yaml
# GCE L4 cloud-burst target.
# endpoint: fill in the static IP from `cd infra/gcp && terraform output -raw endpoint_url`

id: "Qwen/Qwen2.5-7B-Instruct"
family: qwen2.5
size: 7b
revision: "2024-09-19"
quantization: null
runtime: vllm
runtime_version: "0.4.3"
target_host: cloud-burst-l4
endpoint: "http://PLACEHOLDER:8000/v1"
capabilities: [chat]
context_window: 131072
default_sampling:
  temperature: 0.0
  top_p: 1.0
  max_tokens: 256
```

- [ ] **Step 2: Verify manifest loads cleanly**

```bash
cd /Users/huiliang/GitHub/ai-experiments
python -c "
from shared.models.manifest import load_manifest_yaml
from pathlib import Path
m = load_manifest_yaml(Path('shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml'))
print(m.target_host, m.endpoint)
"
```

Expected: prints `cloud-burst-l4 http://PLACEHOLDER:8000/v1`

- [ ] **Step 3: Commit**

```bash
git add shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml
git commit -m "feat: model manifest for qwen2.5-7b on GCE L4 (endpoint placeholder)"
```

---

## Task 8: First terraform apply and smoke test

> This task is manual — no automated tests; the acceptance criterion is a successful eval campaign against the live endpoint.

**Pre-requisites:**
- GCP account with billing enabled
- `gcloud auth application-default login` completed
- L4 GPU quota in `asia-southeast1` (request via GCP console if needed; `g2-standard-8` under "Committed use discounts" or "GPUs (all regions)")
- `terraform` CLI installed (`brew install terraform`)

- [ ] **Step 1: Provision**

```bash
cd infra/gcp
# terraform.tfvars should already have your project_id from Task 4
make up
```

Expected: Terraform creates 4 resources (bucket, IP, firewall, instance). Note the `endpoint_url` output — looks like `http://34.x.x.x:8000/v1`.

- [ ] **Step 2: Fill in the manifest endpoint**

```bash
ENDPOINT=$(terraform output -raw endpoint_url)
echo "endpoint URL: $ENDPOINT"
```

Edit `shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml` — replace `http://PLACEHOLDER:8000/v1` with the actual URL from the output.

- [ ] **Step 3: Wait for vLLM to be ready**

```bash
make health
```

On a cold start this takes ~15 min (HuggingFace pull + GCS cache write). Watch progress via:

```bash
gcloud compute instances get-serial-port-output vllm-eval-server --zone asia-southeast1-b | tail -20
```

- [ ] **Step 4: Run a smoke eval campaign**

```bash
cd /Users/huiliang/GitHub/ai-experiments
uv run python -m shared.eval.runner.cli \
  --model "Qwen/Qwen2.5-7B-Instruct" \
  --gold-set "smoke-v0.0" \
  --judge-config "v0.1" \
  --max-cost-usd 2.00 \
  --template-root experiments/0001-inference-contract-validation/prompt_templates \
  --experiment "0001-inference-contract-validation"
```

Expected: campaign completes, `run.status=completed`, results written to Postgres, cost ~$0.01–$0.05 depending on wall time.

- [ ] **Step 5: Tear down**

```bash
cd infra/gcp
make down
```

Expected: GCE instance and static IP destroyed. GCS bucket (and cached weights) retained.

- [ ] **Step 6: Commit updated manifest**

```bash
cd /Users/huiliang/GitHub/ai-experiments
git add shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml
git commit -m "feat: wire L4 static IP into model manifest (smoke test passed)"
```

---

## After smoke tests: A100 graduation

Once Task 8 passes, add the A100 tier:

1. Add `shared/models/registry/qwen2.5-14b-instruct-vllm-a2.yaml` with `target_host: cloud-burst-a2`.
2. In `terraform.tfvars`, set `instance_type = "a2-highgpu-1g"` and `model_id = "Qwen/Qwen2.5-14B-Instruct"`.
3. `make up` — GCS cache is shared; only new model weights are pulled cold.
4. Update the manifest endpoint.
5. Run campaign, `make down`, commit.
