# GCP Project Bootstrap and Budget Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the dedicated `AI Experiments` Google Cloud project under `huiliang@sgcodecampus.com`, establish keyless Terraform administration, install a USD 100 monthly budget with USD 10/50/100 alerts and automatic Compute Engine shutdown at 100%, and prove the guardrail before any GPU work resumes.

**Architecture:** A one-time, account-guarded gcloud bootstrap creates and bills the project, Terraform service account, and versioned remote-state bucket. Impersonated Terraform then owns the persistent project control plane: APIs, least-privilege runtime identities, budget, Pub/Sub topic, and a second-generation Cloud Run function. Existing L4, judge, and annotation workspaces use separate remote-state prefixes and remain disposable.

**Tech Stack:** Python 3.12, pytest, Ruff, Terraform 1.x, Google provider 5.45.2, Archive provider 2.x, gcloud CLI, Cloud Billing Budgets, Pub/Sub, Cloud Run functions (2nd gen), Eventarc, Cloud Storage, Compute Engine, Make.

## Global Constraints

- Execute from the isolated worktree `/Users/huiliang/GitHub/ai-experiments/.worktrees/operational-recovery` on branch `feature/operational-recovery`.
- Follow red-green-refactor for Python behavior. Run the named RED test before writing implementation code.
- Never activate, modify, or use the `adept` gcloud configuration. Never mutate `adept-prod-497323`.
- The only allowed bootstrap user is exactly `huiliang@sgcodecampus.com`; after the initial global `configurations list` and `auth list` inventory, every gcloud command uses `--configuration=ai-experiments`, and every project resource command uses an explicit `--project`.
- Do not create, download, print, or store a service-account key. Terraform uses impersonated Application Default Credentials.
- The preferred project ID is `sgcc-ai-experiments`. If unavailable, the sole fallback is `sgcc-ai-experiments-66bdf1`, where `66bdf1` is the stable SHA-256 prefix of `huiliang@sgcodecampus.com:ai-experiments`.
- If organization/folder selection, billing-account selection, or USD billing currency is ambiguous, stop before creating or linking the project and obtain the user's explicit selection.
- Project controls are persistent. Never run `terraform destroy` in `infra/gcp/project_controls` during campaign cleanup.
- `google_billing_budget.deletion_policy` is `PREVENT`. Billing stays enabled at 100%; the function stops running VMs only.
- Every disposable VM uses an auto-delete boot disk. After every successful or failed live VM task, delete/destroy it and verify instances, disks, reserved addresses, and campaign buckets are empty.
- Do not resume L4 or A100 work until the synthetic 100% notification has stopped the test VM and the final inventory is empty.

---

### Task 1: Add a canonical project contract and fail-closed target guard

**Files:**
- Create: `shared/gcp/__init__.py`
- Create: `shared/gcp/config.py`
- Create: `tests/shared/gcp/__init__.py`
- Create: `tests/shared/gcp/test_config.py`
- Create: `infra/gcp/project.env.example`

**Interfaces:**
- `ProjectConfig.from_file(path: Path) -> ProjectConfig`
- `ProjectConfig.verify_gcloud(runner=subprocess.run) -> None`
- CLI: `python -m shared.gcp.config --file PATH --check-gcloud`
- Required keys: `GCLOUD_CONFIGURATION`, `GCLOUD_ACCOUNT`, `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_ZONE`, `GCP_TERRAFORM_SERVICE_ACCOUNT`, `GCP_STATE_BUCKET`.

- [ ] **Step 1: Write the failing configuration tests**

Test that the loader rejects missing keys, duplicate keys, shell expansion syntax, and any account other than `huiliang@sgcodecampus.com`. Test that `verify_gcloud` runs exactly:

```python
[
    "gcloud", "config", "get-value", "account",
    "--configuration=ai-experiments",
]
[
    "gcloud", "config", "get-value", "project",
    "--configuration=ai-experiments",
]
```

It must raise `TargetMismatchError` unless the returned account and project exactly match the file. It must also reject `GCLOUD_CONFIGURATION=adept` and `GCP_PROJECT_ID=adept-prod-497323` before calling gcloud.

- [ ] **Step 2: Run the tests to verify RED**

```bash
uv run pytest tests/shared/gcp/test_config.py -v
```

Expected: collection fails because `shared.gcp.config` does not exist.

- [ ] **Step 3: Implement the minimal parser and guard**

Use a frozen dataclass with these field names:

```python
@dataclass(frozen=True)
class ProjectConfig:
    gcloud_configuration: str
    gcloud_account: str
    project_id: str
    region: str
    zone: str
    terraform_service_account: str
    state_bucket: str
```

Parse only non-empty `KEY=value` lines and comments; do not evaluate quotes, `$`, backticks, command substitutions, or `export`. `verify_gcloud` uses `subprocess.run(..., check=True, capture_output=True, text=True, shell=False)` and compares stripped stdout. The CLI exits `0` with `target verified: PROJECT_ID` or exits `2` with the mismatch on stderr.

Create `infra/gcp/project.env.example` with the preferred deterministic values:

```dotenv
GCLOUD_CONFIGURATION=ai-experiments
GCLOUD_ACCOUNT=huiliang@sgcodecampus.com
GCP_PROJECT_ID=sgcc-ai-experiments
GCP_REGION=asia-southeast1
GCP_ZONE=asia-southeast1-b
GCP_TERRAFORM_SERVICE_ACCOUNT=terraform-ai-experiments@sgcc-ai-experiments.iam.gserviceaccount.com
GCP_STATE_BUCKET=sgcc-ai-experiments-tfstate
```

- [ ] **Step 4: Verify GREEN and lint**

```bash
uv run pytest tests/shared/gcp/test_config.py -v
uv run ruff check shared/gcp tests/shared/gcp
```

Expected: all target-guard tests pass and Ruff prints `All checks passed!`.

- [ ] **Step 5: Commit the target guard**

```bash
git add shared/gcp tests/shared/gcp infra/gcp/project.env.example
git commit -m "feat: add fail-closed GCP target guard"
```

---

### Task 2: Implement the idempotent budget shutdown function

**Files:**
- Create: `infra/__init__.py`
- Create: `infra/gcp/__init__.py`
- Create: `infra/gcp/project_controls/__init__.py`
- Create: `infra/gcp/project_controls/function/__init__.py`
- Create: `infra/gcp/project_controls/function/main.py`
- Create: `infra/gcp/project_controls/function/requirements.txt`
- Create: `tests/infra/__init__.py`
- Create: `tests/infra/gcp/__init__.py`
- Create: `tests/infra/gcp/test_budget_shutdown.py`

**Interfaces:**
- `decode_budget_event(cloud_event: Mapping[str, object]) -> dict[str, object]`
- `handle_budget(payload, *, expected_budget_name, expected_project_id, runtime_project_id, instances_client) -> dict[str, object]`
- Cloud Run entry point: `stop_compute_on_budget(cloud_event) -> dict[str, object]`
- Receipt keys: `action`, `project_id`, `cost_amount`, `budget_amount`, `stopped`, `skipped`, `failures`.

- [ ] **Step 1: Write failing unit tests**

Cover all of these cases with a fake aggregated-list client and fake stop operations:

1. cost below budget returns `action="none"` and makes no stop call;
2. cost exactly equal to budget stops every `RUNNING` instance across two zones;
3. cost above budget behaves identically;
4. `TERMINATED`, `STOPPING`, and `SUSPENDED` instances are skipped;
5. duplicate delivery after all instances stop is a successful no-op;
6. one stop failure is recorded while other instances are still attempted;
7. malformed base64, malformed JSON, missing numeric amounts, nonpositive budget, and wrong budget name raise `ValueError` before mutation;
8. `runtime_project_id != expected_project_id` raises `RuntimeError` before listing instances.

- [ ] **Step 2: Run the tests to verify RED**

```bash
uv run pytest tests/infra/gcp/test_budget_shutdown.py -v
```

Expected: collection fails because the function module does not exist.

- [ ] **Step 3: Implement the pure handler and CloudEvent adapter**

The mutation decision is exactly:

```python
if payload["budgetDisplayName"] != expected_budget_name:
    raise ValueError("unexpected budget display name")
if runtime_project_id != expected_project_id:
    raise RuntimeError("runtime project does not match configured project")
cost = Decimal(str(payload["costAmount"]))
budget = Decimal(str(payload["budgetAmount"]))
if budget <= 0:
    raise ValueError("budget amount must be positive")
if cost < budget:
    return no_action_receipt
```

For `cost >= budget`, call `instances_client.aggregated_list(project=expected_project_id)`, derive each zone from the aggregate key's final path component, and call `instances_client.stop(project=expected_project_id, zone=zone, instance=name)`. Wait on each returned operation with `result(timeout=300)`, catch failures per instance, and never call insert, start, delete, billing, disk, bucket, or cross-project APIs.

The entry point reads only `EXPECTED_PROJECT_ID`, `GOOGLE_CLOUD_PROJECT`, and `EXPECTED_BUDGET_NAME`, imports `google.cloud.compute_v1` lazily, decodes `cloud_event.data["message"]["data"]`, and writes one JSON receipt to standard output.

Pin deploy dependencies:

```text
functions-framework==3.10.2
google-cloud-compute==1.49.0
```

- [ ] **Step 4: Verify GREEN and lint**

```bash
uv run pytest tests/infra/gcp/test_budget_shutdown.py -v
uv run ruff check infra/gcp/project_controls/function tests/infra/gcp
```

Expected: all handler tests pass and Ruff passes.

- [ ] **Step 5: Commit the function**

```bash
git add infra/__init__.py infra/gcp/__init__.py infra/gcp/project_controls tests/infra
git commit -m "feat: stop compute on exhausted GCP budget"
```

---

### Task 3: Define the persistent project control plane in Terraform

**Files:**
- Create: `infra/gcp/project_controls/versions.tf`
- Create: `infra/gcp/project_controls/variables.tf`
- Create: `infra/gcp/project_controls/main.tf`
- Create: `infra/gcp/project_controls/outputs.tf`
- Create: `infra/gcp/project_controls/Makefile`
- Create: `infra/gcp/project_controls/terraform.tfvars.example`
- Modify: `infra/gcp/.gitignore`

**Terraform resources:**
- APIs, one source bucket, three service accounts, one custom role, project IAM members, one Pub/Sub topic and publisher binding, one Cloud Run function v2, and one protected project-scoped budget.

- [ ] **Step 1: Create provider and backend declarations**

`versions.tf` must declare Terraform `>= 1.5.0`, an empty `backend "gcs" {}`, Google provider `~> 5.0`, and Archive provider `~> 2.4`. Configure Google with `project`, `region`, `billing_project = var.project_id`, and `user_project_override = true`.

- [ ] **Step 2: Declare validated inputs**

Declare `project_id`, `billing_account_id`, `region` (default `asia-southeast1`), `budget_amount_usd` (default `100` and validation `> 0`), `budget_display_name` (default `ai-experiments-monthly`), and `function_name` (default `budget-stop-compute`). The committed example tfvars contains only non-secret preferred values and a syntactically fake billing ID `000000-000000-000000`.

- [ ] **Step 3: Define APIs and least-privilege identities**

Enable these exact services with `disable_on_destroy = false`:

```hcl
toset([
  "artifactregistry.googleapis.com",
  "billingbudgets.googleapis.com",
  "cloudbuild.googleapis.com",
  "cloudfunctions.googleapis.com",
  "compute.googleapis.com",
  "eventarc.googleapis.com",
  "logging.googleapis.com",
  "pubsub.googleapis.com",
  "run.googleapis.com",
  "storage.googleapis.com",
])
```

Create `budget-compute-stop` as the function runtime identity, `budget-event-trigger` as the Eventarc trigger identity, and `budget-function-build` as the Cloud Build identity. Create a project custom role `budgetComputeStopper` with only:

```hcl
permissions = [
  "compute.instances.get",
  "compute.instances.list",
  "compute.instances.stop",
]
```

Grant the runtime identity that custom role plus `roles/logging.logWriter`. Grant the trigger identity `roles/eventarc.eventReceiver` and `roles/run.invoker`. Grant the build identity only `roles/logging.logWriter`, `roles/artifactregistry.writer`, and `roles/storage.objectViewer`, as required by the current Cloud Run functions custom-build-identity guidance. Do not grant these identities Owner, Editor, Compute Admin, Service Account Token Creator, Storage Admin, or Billing roles.

- [ ] **Step 4: Define Pub/Sub, function source, and Cloud Run function**

Create topic `budget-updates`. Grant `roles/pubsub.publisher` on that topic to:

```text
serviceAccount:billingbudgets-notification@system.gserviceaccount.com
```

Create a Singapore-region, uniform-access, public-access-prevented source bucket named `${var.project_id}-function-source`. Archive only `function/`; name the uploaded object `budget-stop-${data.archive_file.function.output_md5}.zip`.

Deploy `google_cloudfunctions2_function.budget_stop` in `asia-southeast1`, runtime `python312`, entry point `stop_compute_on_budget`, build service account `google_service_account.function_build.id`, 256 MiB, timeout 540 seconds, max instance count 1, runtime service account `budget-compute-stop`, environment variables `EXPECTED_PROJECT_ID` and `EXPECTED_BUDGET_NAME`, and an Eventarc Pub/Sub `messagePublished` trigger on `budget-updates` using `budget-event-trigger`. Set retry policy to retry; handler idempotency makes duplicate delivery safe. Make the function depend on all three build-role bindings so IAM propagation completes before the build begins.

- [ ] **Step 5: Define the protected project budget**

Use `data.google_project.current.number` and create exactly:

```hcl
resource "google_billing_budget" "project" {
  billing_account = var.billing_account_id
  display_name    = var.budget_display_name
  deletion_policy = "PREVENT"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }
  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }
  threshold_rules { threshold_percent = 0.10 }
  threshold_rules { threshold_percent = 0.50 }
  threshold_rules { threshold_percent = 1.00 }
  all_updates_rule {
    pubsub_topic                   = google_pubsub_topic.budget_updates.id
    schema_version                 = "1.0"
    enable_project_level_recipients = true
  }
}
```

Make the budget depend on the topic publisher binding. Output the budget resource name, topic ID, function name, runtime service-account email, source bucket name, and project number.

- [ ] **Step 6: Add guarded Make targets**

The Makefile must include `../project.env`, export `TF_VAR_project_id=$(GCP_PROJECT_ID)`, and define `guard`, `init`, `validate`, `plan`, and `apply`. `guard` runs the Task 1 CLI from the repo root. `init` uses:

```bash
terraform init -reconfigure \
  -backend-config="bucket=$(GCP_STATE_BUCKET)" \
  -backend-config="prefix=project-controls"
```

There is deliberately no `down` or `destroy` target.

- [ ] **Step 7: Format, initialize without a backend, and validate**

```bash
terraform -chdir=infra/gcp/project_controls fmt -recursive
terraform -chdir=infra/gcp/project_controls init -backend=false
terraform -chdir=infra/gcp/project_controls validate
```

Expected: initialization succeeds, validation prints `Success!`, and `.terraform.lock.hcl` locks Google 5.45.2 plus a compatible Archive 2.x release.

- [ ] **Step 8: Commit the control plane**

```bash
git add infra/gcp/project_controls infra/gcp/.gitignore
git commit -m "feat: define persistent GCP budget controls"
```

---

### Task 4: Write the audited bootstrap and recovery runbook

**Files:**
- Create: `docs/runbooks/gcp-ai-experiments-bootstrap.md`
- Create: `infra/gcp/state-lifecycle.json`
- Modify: `README.md`

- [ ] **Step 1: Document the preflight and hard stop**

The runbook begins by proving the current working tree and recording the existing active configuration without changing it:

```bash
git status --short
gcloud config configurations list
gcloud auth list
```

Then create the isolated configuration without activating it and authenticate only the approved account:

```bash
gcloud config configurations create ai-experiments --no-activate
gcloud auth login huiliang@sgcodecampus.com --configuration=ai-experiments
gcloud config set account huiliang@sgcodecampus.com --configuration=ai-experiments
```

Every later command retains the explicit configuration flag. State that execution stops if the exact account is absent from `gcloud auth list`.

- [ ] **Step 2: Document deterministic discovery and selection**

Include exact read-only commands for organizations, folders, open billing accounts, and visible projects. Record the chosen parent as either `--organization=NUMBER`, `--folder=NUMBER`, or no parent only after user confirmation. If more than one open billing account exists, stop for selection. Require the user to verify in the Billing console that the selected billing account accepts USD budgets before linking it.

Probe `sgcc-ai-experiments`; if unavailable, use only `sgcc-ai-experiments-66bdf1`. Record `PROJECT_ID`, `PARENT_FLAG`, and `BILLING_ACCOUNT_ID` in the execution ledger before the create command.

- [ ] **Step 3: Document project, billing, identity, and state creation**

Use explicit commands for `gcloud projects create`, `gcloud billing projects link`, bootstrap API enablement, Terraform service-account creation, user `roles/iam.serviceAccountTokenCreator`, project roles, billing-account `roles/billing.costsManager`, and bucket creation. The Terraform service account receives no Owner role and no key.

Bootstrap project roles are exactly:

```text
roles/artifactregistry.admin
roles/cloudfunctions.admin
roles/compute.admin
roles/eventarc.admin
roles/iam.roleAdmin
roles/iam.serviceAccountAdmin
roles/iam.serviceAccountUser
roles/pubsub.admin
roles/resourcemanager.projectIamAdmin
roles/run.admin
roles/serviceusage.serviceUsageAdmin
roles/storage.admin
```

Create `gs://${PROJECT_ID}-tfstate` in `asia-southeast1` with uniform bucket access, public access prevention, versioning, and the lifecycle file below. Grant the Terraform service account `roles/storage.admin` on this bucket only.

`infra/gcp/state-lifecycle.json` is exactly:

```json
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"daysSinceNoncurrentTime": 30, "numNewerVersions": 10}
    }
  ]
}
```

- [ ] **Step 4: Document keyless ADC and verification**

```bash
gcloud auth application-default login \
  --impersonate-service-account="terraform-ai-experiments@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud auth application-default set-quota-project "${PROJECT_ID}"
gcloud auth application-default print-access-token >/dev/null
```

Verify the ADC JSON contains the exact service-account impersonation URL without printing tokens or source credentials. Then create `infra/gcp/project.env` with the actual project values and run the Task 1 guard.

- [ ] **Step 5: Document partial-failure recovery**

For each bootstrap stage, list the corresponding read-only describe/list command. State explicitly: do not delete the project, unlink billing, or remove the state bucket automatically after a partial failure; record existing resources and resume idempotently after diagnosis.

- [ ] **Step 6: Link the runbook and commit**

```bash
git add docs/runbooks/gcp-ai-experiments-bootstrap.md infra/gcp/state-lifecycle.json README.md
git commit -m "docs: add guarded GCP bootstrap runbook"
```

---

### Task 5: Execute the one-time project bootstrap and record the canonical target

**Files:**
- Create: `infra/gcp/project.env`
- Create: `docs/notes/gcp-bootstrap-2026-07-22.md`
- Modify: `.superpowers/sdd/progress.md` (ignored local execution ledger)

- [ ] **Step 1: Reconfirm the prior incident evidence without accessing Adept**

Review the recorded failed applies, empty Terraform state, and final empty inventories from the earlier recovery attempt. Record that no resource creation reached Google Cloud. Do not authenticate to, inventory, destroy, edit IAM, or change billing in the Adept account; it is out of scope for this project.

- [ ] **Step 2: Authenticate and perform discovery**

Follow Task 4 through account login and discovery. Record command outputs with account numbers and IDs but no access tokens. If the parent, billing account, or USD currency check is ambiguous, stop this task and ask the user; do not proceed by choosing the first result.

- [ ] **Step 3: Create and link the project**

Create `AI Experiments` using the preferred or deterministic fallback ID and confirmed parent, then link the confirmed billing account. Immediately verify:

```bash
gcloud projects describe "${PROJECT_ID}" --configuration=ai-experiments
gcloud billing projects describe "${PROJECT_ID}" --configuration=ai-experiments
```

- [ ] **Step 4: Create the Terraform bridge and remote-state bucket**

Enable bootstrap APIs, create the Terraform service account, apply the exact project and billing roles from Task 4, grant only `huiliang@sgcodecampus.com` token creation on that account, and create the protected state bucket. Verify that `gcloud iam service-accounts keys list` reports only Google-managed system keys and no user-managed key.

- [ ] **Step 5: Replace ADC with impersonated credentials and verify the target**

Run the keyless ADC commands, create `infra/gcp/project.env` with actual values, and run:

```bash
uv run python -m shared.gcp.config --file infra/gcp/project.env --check-gcloud
```

Expected: `target verified: PROJECT_ID`.

- [ ] **Step 6: Remove stale ignored Adept runtime files only after the empty-state check**

Confirm each local state has zero resources:

```bash
terraform -chdir=infra/gcp show -json | jq '.values.root_module.resources // [] | length'
terraform -chdir=infra/gcp/judge show -json | jq '.values.root_module.resources // [] | length'
terraform -chdir=infra/gcp/annotation show -json | jq '.values.root_module.resources // [] | length'
```

Expected: `0` for every state that exists. Then delete only ignored `terraform.tfvars`, `terraform.tfstate`, and `terraform.tfstate.backup` files under these three workspaces. Do not delete tracked lock files or Terraform source.

- [ ] **Step 7: Record and commit the canonical target**

The note records project ID/number, parent, billing account ID, service-account emails, state bucket, APIs, role grants, key inventory, and timestamps. Do not record tokens or secrets.

```bash
git add infra/gcp/project.env docs/notes/gcp-bootstrap-2026-07-22.md
git commit -m "ops: record AI Experiments GCP project"
```

---

### Task 6: Apply and verify the persistent budget control plane

**Files:**
- Modify: `docs/notes/gcp-bootstrap-2026-07-22.md`

- [ ] **Step 1: Run local gates before plan**

```bash
uv run pytest tests/shared/gcp/test_config.py tests/infra/gcp/test_budget_shutdown.py -v
uv run ruff check shared/gcp infra/gcp/project_controls/function tests/shared/gcp tests/infra/gcp
terraform -chdir=infra/gcp/project_controls fmt -check -recursive
```

Expected: all pass.

- [ ] **Step 2: Initialize remote state and create a reviewed plan**

From `infra/gcp/project_controls`, run the Make `guard` and `init` targets, then:

```bash
terraform plan -input=false \
  -var="billing_account_id=${BILLING_ACCOUNT_ID}" \
  -out=project-controls.tfplan
terraform show -no-color project-controls.tfplan
```

Confirm the plan has no VM, disk, address, billing unlink, project deletion, service-account key, or cross-project resource.

- [ ] **Step 3: Apply the saved plan**

```bash
terraform apply -input=false project-controls.tfplan
```

On failure, do not destroy the control workspace. Capture the error, inspect state and live resources, fix forward, and re-plan.

- [ ] **Step 4: Verify the budget and automation live**

Use Terraform outputs plus explicit gcloud/API reads to verify:

- budget amount is USD 100 and numeric-project scope is exact;
- current-spend thresholds are `0.10`, `0.50`, and `1.00`;
- project-level recipients and Pub/Sub updates are enabled;
- deletion policy is `PREVENT`;
- topic IAM includes only the required billing publisher plus administrative bindings;
- function is ACTIVE in `asia-southeast1` with the expected runtime identity and environment;
- runtime custom role contains only get/list/stop and logging writer is separate.

- [ ] **Step 5: Record outputs and commit evidence**

Append resource names and verification results to the bootstrap note without secrets.

```bash
git add docs/notes/gcp-bootstrap-2026-07-22.md
git commit -m "ops: verify GCP budget control plane"
```

---

### Task 7: Prove automatic shutdown with a disposable VM

**Files:**
- Create: `infra/gcp/project_controls/test_vm.tf`
- Create: `infra/gcp/project_controls/test.auto.tfvars.example`
- Create: `docs/notes/gcp-budget-shutdown-test-2026-07-22.md`

- [ ] **Step 1: Add an opt-in test VM resource**

Define `enable_shutdown_test` defaulting to `false`. With `true`, create exactly one `e2-micro` instance named `budget-shutdown-test` in the canonical zone, use the current `debian-12` family, no service-account scopes, no static address, labels `purpose=budget-shutdown-test` and `disposable=true`, and an auto-delete 10 GiB balanced boot disk. Add no firewall rule.

- [ ] **Step 2: Format, validate, and commit the disabled fixture**

```bash
terraform -chdir=infra/gcp/project_controls fmt -recursive
terraform -chdir=infra/gcp/project_controls validate
git add infra/gcp/project_controls/test_vm.tf infra/gcp/project_controls/test.auto.tfvars.example
git commit -m "test: add disposable budget shutdown fixture"
```

- [ ] **Step 3: Create the test VM with a saved plan**

Plan with `-var=enable_shutdown_test=true`, inspect that the only new paid resource is the one VM and its auto-delete boot disk, then apply the saved plan. Verify instance status is `RUNNING`.

- [ ] **Step 4: Publish the synthetic 100% message**

Publish this JSON to the Terraform-output topic using the explicit configuration and project:

```json
{
  "budgetDisplayName": "ai-experiments-monthly",
  "costAmount": 100.0,
  "budgetAmount": 100.0,
  "budgetAmountType": "SPECIFIED_AMOUNT",
  "alertThresholdExceeded": 1.0,
  "currencyCode": "USD"
}
```

Poll for at most five minutes. Expected: VM status becomes `TERMINATED`, and function logs contain a structured receipt naming `budget-shutdown-test` in `stopped` with no failure.

- [ ] **Step 5: Prove idempotency**

Publish the same message a second time. Expected: the VM remains `TERMINATED`, the receipt is a successful no-op, and no new resource appears.

- [ ] **Step 6: Destroy the disposable fixture and inventory the project**

Apply with `enable_shutdown_test=false`; do not destroy the control workspace. Verify the instance and boot disk are gone. Then list all instances, disks, reserved addresses, and buckets. Only the state and function-source buckets may remain; no campaign bucket may exist.

- [ ] **Step 7: Record and commit test evidence**

Record timestamps, message payload hash, VM state transition, function receipt, cleanup apply result, and final inventory.

```bash
git add docs/notes/gcp-budget-shutdown-test-2026-07-22.md
git commit -m "ops: prove automatic budget shutdown"
```

---

### Task 8: Move disposable workspaces to guarded remote state

**Files:**
- Modify: `infra/gcp/main.tf`
- Modify: `infra/gcp/Makefile`
- Modify: `infra/gcp/terraform.tfvars.example`
- Modify: `infra/gcp/judge/main.tf`
- Modify: `infra/gcp/judge/Makefile`
- Modify: `infra/gcp/annotation/main.tf`
- Modify: `infra/gcp/annotation/Makefile`

- [ ] **Step 1: Add empty GCS backend blocks**

Add `backend "gcs" {}` to all three Terraform blocks. Do not hardcode a bucket or project in HCL.

- [ ] **Step 2: Add project guards and explicit state prefixes**

Each Makefile includes the canonical `project.env`, exports `TF_VAR_project_id`, runs the Task 1 guard before `up`, `down`, `ssh`, or `tunnel`, and initializes these exact prefixes:

```text
infra/gcp              -> eval-l4
infra/gcp/judge        -> judge-a100
infra/gcp/annotation   -> annotation
```

Every gcloud command includes `--configuration=$(GCLOUD_CONFIGURATION)` and `--project=$(GCP_PROJECT_ID)`. Keep campaign `down` targets because those workspaces are disposable.

- [ ] **Step 3: Remove executable placeholders**

Change `infra/gcp/terraform.tfvars.example` to explain that `project_id` comes from `project.env`/`TF_VAR_project_id`; remove `your-gcp-project-id`. Do not copy the billing account or service-account credentials into campaign tfvars.

- [ ] **Step 4: Initialize and validate each remote workspace**

Because Task 5 proved local state empty, use `terraform init -reconfigure` with the matching bucket and prefix; do not use `-migrate-state` against an unknown/nonempty local state. Then run `terraform validate` in all three directories.

- [ ] **Step 5: Verify empty remote campaign state**

For each workspace, run `terraform state list`. Expected: no resources. Run explicit live inventories; expected: no disposable instances, disks, reserved addresses, or campaign buckets.

- [ ] **Step 6: Commit the workspace migration**

```bash
git add infra/gcp/main.tf infra/gcp/Makefile infra/gcp/terraform.tfvars.example \
  infra/gcp/judge/main.tf infra/gcp/judge/Makefile \
  infra/gcp/annotation/main.tf infra/gcp/annotation/Makefile
git commit -m "build: guard GCP campaign remote state"
```

---

### Task 9: Remove active Adept targeting and run the completion gate

**Files:**
- Modify: `docs/superpowers/specs/2026-07-17-operational-recovery-design.md`
- Modify: `docs/superpowers/plans/2026-07-18-tranche1-repository-recovery.md`
- Modify: `docs/superpowers/plans/2026-07-18-tranche2-safe-cloud-lifecycle.md`
- Modify: `docs/superpowers/plans/2026-07-18-tranche3-general-curation-slice.md`
- Modify: `docs/notes/rebaseline-2026-07-18.md`
- Modify: `.superpowers/sdd/progress.md` (ignored local execution ledger)

- [ ] **Step 1: Preserve incident history but disable stale commands**

Keep the factual record that Adept was inspected and zero resources were created. Mark old executable cloud tasks `SUPERSEDED — DO NOT RUN`; replace their active account/project commands with links to the canonical `infra/gcp/project.env` and the new bootstrap runbook. No executable command may contain `adept-prod-497323`.

- [ ] **Step 2: Run the repository target scan**

```bash
rg -n "adept-prod-497323|your-gcp-project-id" . \
  -g '!docs/superpowers/specs/2026-07-22-gcp-project-bootstrap-budget-controls-design.md' \
  -g '!docs/notes/gcp-bootstrap-2026-07-22.md'
```

Expected: only explicitly labeled historical prose and fail-closed target-guard test sentinels, never a runnable cloud command, tfvars value, Make target, or current targeting instruction. Manually inspect every result.

- [ ] **Step 3: Run the full static suite**

```bash
uv run pytest -q
uv run ruff check .
terraform -chdir=infra/gcp/project_controls fmt -check -recursive
terraform -chdir=infra/gcp/project_controls validate
terraform -chdir=infra/gcp validate
terraform -chdir=infra/gcp/judge validate
terraform -chdir=infra/gcp/annotation validate
```

Expected: all tests/lint/validation pass.

- [ ] **Step 4: Run the final live gate**

Verify the canonical target guard, impersonated ADC, linked billing account, protected USD 100 budget, three alert thresholds, healthy topic/function, successful synthetic shutdown receipt, and empty disposable inventory. Verify no user-managed service-account keys exist.

- [ ] **Step 5: Commit documentation corrections**

```bash
git add docs/superpowers/specs/2026-07-17-operational-recovery-design.md \
  docs/superpowers/plans/2026-07-18-tranche1-repository-recovery.md \
  docs/superpowers/plans/2026-07-18-tranche2-safe-cloud-lifecycle.md \
  docs/superpowers/plans/2026-07-18-tranche3-general-curation-slice.md \
  docs/notes/rebaseline-2026-07-18.md
git commit -m "docs: supersede incorrect Adept cloud target"
```

- [ ] **Step 6: Request final code review and mark the gate**

Use `superpowers:requesting-code-review`, address findings, rerun affected checks, and record in `.superpowers/sdd/progress.md` that project bootstrap/budget controls are complete. Only then unblock the previous L4 live campaign, using `infra/gcp/project.env` and the `eval-l4` remote-state prefix.
