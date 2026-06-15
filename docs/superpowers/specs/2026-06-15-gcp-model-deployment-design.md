# GCP Model Deployment Design

**Date:** 2026-06-15
**Status:** Approved

## Context

Phase 1's acceptance criteria require the eval substrate to reach a third sovereign deployment target: a measured on-demand cloud-burst instance. The DGX Spark (the always-on sovereign anchor) is arriving imminently. This sprint wires the GCP cloud-burst path in parallel so eval campaigns can run on GCP immediately, without waiting for the Spark bring-up to complete.

The ROADMAP already names GCE A3 as the on-demand sovereign target and the manifest schema already anticipates `cloud-burst-a3`. This design introduces the L4 tier first (cheaper, sufficient for 7B/14B models), graduates to A100 after smoke tests pass, and lays the groundwork for A3 (H100) later.

---

## Scope

- Terraform-managed GCE instances (L4 → A100) with vLLM serving an OpenAI-compatible endpoint.
- GCS bucket as a model weight cache (warm spin-up after first pull).
- New `target_host` values, model manifest YAMLs, and rate card YAMLs wired into the existing eval runner.
- A `Makefile` wrapping common provisioning commands.

Out of scope: Artifact Registry, CI/CD pipelines for image builds, remote Terraform state, Kubernetes, Vertex AI.

---

## Section 1 — Infrastructure layout

**Directory:** `infra/gcp/`

| File | Purpose |
|---|---|
| `main.tf` | GCP provider, GCE instance, GCS bucket, firewall rule (TCP 8000 inbound), reserved static external IP |
| `variables.tf` | `project_id`, `zone` (default `asia-southeast1-b`), `instance_type` (default `g2-standard-8` for L4), `model_id`, `vllm_version`, `hf_token` (sensitive), `preemptible` (default `true`) |
| `outputs.tf` | `endpoint_url` — `http://<static-ip>:8000/v1`; `instance_name`; `bucket_name` |
| `startup.sh.tpl` | Startup script template; parameterized on `model_id`, `bucket_name`, `hf_token` |
| `Makefile` | `make up`, `make down`, `make health` wrappers |
| `.gitignore` | Ignores `*.tfstate`, `*.tfstate.backup`, `.terraform/`, `*.tfvars` (secrets) |

**GCP resources provisioned:**

- **GCE instance** — Deep Learning VM image (`common-dl-gpu-debian-11-py310`), preemptible/spot by default, CUDA + Docker pre-installed. Instance type parameterized; default `g2-standard-8` (1× L4 24 GB VRAM).
- **GCS bucket** — `ai-experiments-model-cache`, `asia-southeast1`. `prevent_destroy = true` so weights survive `terraform destroy`. Keyed by model ID (`gs://<bucket>/<model_id>/`).
- **Reserved static external IP** — stable across stop/start cycles; recorded in committed manifest YAMLs.
- **Firewall rule** — allows TCP 8000 inbound; scoped to instances tagged `vllm-server`.

**State:** local `.tfstate` in `infra/gcp/` (gitignored). No remote backend at this stage.

---

## Section 2 — Startup script & vLLM serving

The rendered `startup.sh` runs once via GCE `metadata_startup_script`. Steps:

1. **Model cache check** — `gsutil -m cp -r gs://<bucket>/<model_id>/ /model/` if the GCS path exists; otherwise `huggingface-cli download <model_id> --local-dir /model/`, then `gsutil -m cp -r /model/ gs://<bucket>/<model_id>/` to seed the cache.

2. **Start vLLM** — run the pinned vLLM Docker image (`vllm/vllm-openai:<vllm_version>`) with:
   - `--gpus all`
   - `--model /model`
   - `--served-model-name <model_id>`
   - `--host 0.0.0.0 --port 8000`
   - `--restart unless-stopped`

3. **Health-gate** — `until curl -sf http://localhost:8000/health; do sleep 5; done` with a log line on completion. Serial console output captures this signal.

**Startup time:**
- Warm (GCS cache hit): ~1–2 minutes.
- Cold (HuggingFace pull + cache write): ~10–15 minutes for a 7B model.

vLLM version is pinned via `var.vllm_version` (e.g. `v0.4.3`) — not `latest`.

---

## Section 3 — Manifest & rate card additions

**Schema change (`shared/models/manifest.py`):**

`target_host` Literal gains two values:
```python
target_host: Literal["mac", "spark", "cloud-burst-l4", "cloud-burst-a2", "cloud-burst-a3", "cloud-burst-p5"]
```

**New model manifest YAMLs (`shared/models/registry/`):**

`qwen2.5-7b-instruct-vllm-l4.yaml` (added now):
```yaml
id: "Qwen/Qwen2.5-7B-Instruct"
family: qwen2.5
size: 7b
revision: "2024-09-19"
quantization: null
runtime: vllm
runtime_version: "0.4.3"
target_host: cloud-burst-l4
endpoint: "http://<static-ip>:8000/v1"
capabilities: [chat]
context_window: 131072
default_sampling:
  temperature: 0.0
  top_p: 1.0
  max_tokens: 256
```

`qwen2.5-14b-instruct-vllm-a2.yaml` (added after smoke tests pass).

**New rate cards (`shared/eval/cost/rate_cards/`):**

`cloud-burst-l4.yaml`:
```yaml
target_host: cloud-burst-l4
unit: per_hour
prompt_usd_per_mtok: 0.0
completion_usd_per_mtok: 0.0
wall_usd_per_hour: 0.70
```

`cloud-burst-a2.yaml`:
```yaml
target_host: cloud-burst-a2
unit: per_hour
prompt_usd_per_mtok: 0.0
completion_usd_per_mtok: 0.0
wall_usd_per_hour: 2.50
```

**Privacy guardrail:** `cloud-burst-*` targets are Tier 1 sovereign (we control the runtime and data flow). The guardrail's `never_to_third_party` check does not apply to these targets. No guardrail logic changes required.

---

## Section 4 — End-to-end workflow

```
make up          # terraform apply; ~2 min warm, ~15 min cold
make health      # curl endpoint /health — polls until 200
# ... run eval campaign via runner pointing at manifest YAML ...
make down        # terraform destroy; GCS bucket and weights persist
```

**First run (cold):**
1. `cd infra/gcp && terraform init`
2. `cp terraform.tfvars.example terraform.tfvars` — fill in `project_id`, `hf_token`
3. `make up` — provisions instance, static IP, bucket; starts vLLM (~15 min)
4. `make health` — confirms endpoint is live
5. Run campaign: `python -m shared.eval.runner.runner --manifest shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml ...`
6. `make down` — destroys instance; bucket retained

**Graduating to A100:**
- Change `instance_type = "a2-highgpu-1g"` in `terraform.tfvars`
- Change `model_id` to the larger model
- `make up` — GCS cache shared across instance types (same bucket, keyed by model ID); first A100 run is cold for the new model only

**Makefile targets:**

| Target | Command |
|---|---|
| `up` | `terraform apply -auto-approve` |
| `down` | `terraform destroy -auto-approve` |
| `health` | `until curl -sf $$(terraform output -raw endpoint_url)/health; do sleep 5; done` |
| `ssh` | `gcloud compute ssh $$(terraform output -raw instance_name) --zone $(ZONE)` |

---

## Execution order

1. Add `cloud-burst-l4` and `cloud-burst-a2` to `manifest.py` Literal.
2. Write `infra/gcp/` Terraform files and `Makefile`.
3. Add `cloud-burst-l4.yaml` rate card.
4. Add `qwen2.5-7b-instruct-vllm-l4.yaml` model manifest (static IP filled in after first `terraform apply`).
5. Smoke-test: `make up` → `make health` → one eval campaign → `make down`.
6. After smoke tests pass: add A100 rate card and 14B manifest.

---

## Out of scope

- Remote Terraform state (S3/GCS backend) — not needed at one-person scale yet.
- Artifact Registry / pre-built Docker images — startup script + GCS cache is sufficient.
- Kubernetes / GKE — overkill for batch eval campaigns.
- Vertex AI Model Garden — not sovereign by the project's definition (managed runtime).
- `cloud-burst-a3` (H100) wiring — the Literal already includes it; a manifest + rate card follow once A100 smoke tests pass and the Spark bring-up is assessed.
