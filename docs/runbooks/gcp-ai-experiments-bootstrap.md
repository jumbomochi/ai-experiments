# GCP AI Experiments bootstrap and recovery

This runbook is the audited, one-time bridge from an approved administrator account to the
repository's dedicated GCP project and keyless Terraform identity. It does not apply the
Terraform control plane or create campaign compute. Keep GPU execution blocked until the later
project-control verification gate is complete.

Run commands from the repository root. Use the ignored local file `.superpowers/sdd/progress.md`
as the execution ledger. Record command timestamps, selected identifiers, output, and errors, but
never record access tokens, refresh tokens, source credentials, or other secrets.

## 1. Preflight and hard stop

First prove the working tree and record the existing global gcloud state without changing it:

```bash
git status --short
gcloud config configurations list
gcloud auth list
```

Do not activate, edit, or use any existing configuration for this repository. Create the isolated
configuration without activating it, then authenticate only the approved account:

```bash
gcloud config configurations create ai-experiments --no-activate
gcloud auth login huiliang@sgcodecampus.com --configuration=ai-experiments
gcloud config set account huiliang@sgcodecampus.com --configuration=ai-experiments
gcloud auth list --filter="account=huiliang@sgcodecampus.com" --format="value(account)" --configuration=ai-experiments
```

The final command must print exactly `huiliang@sgcodecampus.com`. Stop if that exact account is
absent, another account is selected, or authentication is uncertain. From this point onward every
gcloud command must retain `--configuration=ai-experiments`; project-resource commands must also
name the project explicitly.

If the configuration already exists during a recovery, do not recreate it. Inspect it with:

```bash
gcloud config list --configuration=ai-experiments
gcloud auth list --configuration=ai-experiments
```

Stop unless the account property is exactly the approved account. The project property may be
unset before creation, but it must not point at an unrelated project.

## 2. Discover and select deterministically

Discovery is read-only. Capture all results in the execution ledger:

```bash
gcloud organizations list --configuration=ai-experiments
gcloud billing accounts list --filter="open=true" --configuration=ai-experiments
gcloud projects list --configuration=ai-experiments
```

After the user selects exactly one organization, list its top-level folders. If a folder is a
candidate parent, list its children as needed:

```bash
gcloud resource-manager folders list --organization="ORGANIZATION_NUMBER" --configuration=ai-experiments
gcloud resource-manager folders list --folder="PARENT_FOLDER_NUMBER" --configuration=ai-experiments
```

Fail closed on parent selection:

- If more than one organization or folder is plausible, stop for explicit user selection.
- Record exactly one parent choice as `--organization=NUMBER`, `--folder=NUMBER`, or `no parent`.
- Use `no parent` only after the user explicitly confirms it; never infer it from an empty or
  inaccessible listing.
- If no open billing account is visible, stop. If more than one is open, stop for explicit user
  selection. Do not choose the first result.
- Before linking, require the user to verify in the Google Cloud Billing console that the selected
  billing account uses SGD as its currency. Stop if it does not or the answer is unclear.

Probe the preferred ID first:

```bash
gcloud projects describe sgcc-ai-experiments --project=sgcc-ai-experiments --configuration=ai-experiments
```

If the project is visible, determine whether it is an earlier partial bootstrap and resume only
after confirming ownership and the ledger. If the response is `NOT_FOUND`, the ID is a candidate
for creation; the create response remains authoritative. Any permission, network, or other error
is ambiguous and must stop execution.

If creation authoritatively reports that the preferred ID is unavailable, the only allowed
fallback is `sgcc-ai-experiments-66bdf1`. Probe it the same way and stop if it is unavailable or
ambiguous:

```bash
gcloud projects describe sgcc-ai-experiments-66bdf1 --project=sgcc-ai-experiments-66bdf1 --configuration=ai-experiments
```

Before any create command, add a ledger entry containing all three decisions:

| Field | Allowed value |
|---|---|
| `PROJECT_ID` | `sgcc-ai-experiments` or, only after an unavailable result, `sgcc-ai-experiments-66bdf1` |
| `PARENT_FLAG` | `--organization=NUMBER`, `--folder=NUMBER`, or explicitly confirmed `no parent` |
| `BILLING_ACCOUNT_ID` | the explicitly confirmed open account that uses SGD as its currency |

Set local shell values from that reviewed ledger entry:

```bash
PROJECT_ID="REVIEWED_PROJECT_ID"
BILLING_ACCOUNT_ID="REVIEWED_BILLING_ACCOUNT_ID"
TF_SERVICE_ACCOUNT="terraform-ai-experiments@${PROJECT_ID}.iam.gserviceaccount.com"
STATE_BUCKET="${PROJECT_ID}-tfstate"
```

Do not proceed until the literal values have been reviewed and the placeholders are gone.

## 3. Create and link the project

Run exactly one parent-specific create command matching `PARENT_FLAG` in the ledger.

Organization parent:

```bash
gcloud projects create "${PROJECT_ID}" --name="AI Experiments" --organization="ORGANIZATION_NUMBER" --configuration=ai-experiments
```

Folder parent:

```bash
gcloud projects create "${PROJECT_ID}" --name="AI Experiments" --folder="FOLDER_NUMBER" --configuration=ai-experiments
```

Explicitly confirmed no parent:

```bash
gcloud projects create "${PROJECT_ID}" --name="AI Experiments" --configuration=ai-experiments
```

If the preferred create returns `ALREADY_EXISTS`, record the failed attempt, probe the one allowed
fallback, update and re-review the ledger, recompute the local values, and only then run the
matching create command with the fallback. For any other failure, stop and use the recovery table
below; do not guess whether the project was created.

Set the new project only inside the isolated configuration, verify it, and link the reviewed
billing account:

```bash
gcloud config set project "${PROJECT_ID}" --configuration=ai-experiments
gcloud projects describe "${PROJECT_ID}" --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud billing projects link "${PROJECT_ID}" --billing-account="${BILLING_ACCOUNT_ID}" --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud billing projects describe "${PROJECT_ID}" --project="${PROJECT_ID}" --configuration=ai-experiments
```

The billing description must identify exactly the reviewed billing account and report billing as
enabled. Stop on a mismatch.

## 4. Enable bootstrap APIs and create the Terraform identity

Enable only the APIs needed by the committed project controls and campaign workspaces:

```bash
gcloud services enable artifactregistry.googleapis.com billingbudgets.googleapis.com cloudbilling.googleapis.com cloudbuild.googleapis.com cloudfunctions.googleapis.com cloudresourcemanager.googleapis.com compute.googleapis.com eventarc.googleapis.com iam.googleapis.com iamcredentials.googleapis.com logging.googleapis.com monitoring.googleapis.com pubsub.googleapis.com run.googleapis.com serviceusage.googleapis.com storage.googleapis.com --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud services list --enabled --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud services describe iam.googleapis.com --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud services describe iamcredentials.googleapis.com --project="${PROJECT_ID}" --configuration=ai-experiments
```

Both service descriptions must report `state: ENABLED`. The Service Account Credentials API is
required before the later ADC flow can mint short-lived impersonated credentials.

Create the dedicated Terraform service account and allow only the approved user to mint its
short-lived tokens:

```bash
gcloud iam service-accounts create terraform-ai-experiments --display-name="Terraform AI Experiments" --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud iam service-accounts add-iam-policy-binding "${TF_SERVICE_ACCOUNT}" --member="user:huiliang@sgcodecampus.com" --role="roles/iam.serviceAccountTokenCreator" --project="${PROJECT_ID}" --configuration=ai-experiments
```

Grant the Terraform service account exactly these project roles—no Owner role and no additional
project role:

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

Apply the exact list:

```bash
for ROLE in \
  roles/artifactregistry.admin \
  roles/cloudfunctions.admin \
  roles/compute.admin \
  roles/eventarc.admin \
  roles/iam.roleAdmin \
  roles/iam.serviceAccountAdmin \
  roles/iam.serviceAccountUser \
  roles/pubsub.admin \
  roles/resourcemanager.projectIamAdmin \
  roles/run.admin \
  roles/serviceusage.serviceUsageAdmin \
  roles/storage.admin
do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${TF_SERVICE_ACCOUNT}" --role="${ROLE}" --project="${PROJECT_ID}" --configuration=ai-experiments
done
```

Grant the billing-account permission needed to manage the project budget:

```bash
gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" --member="serviceAccount:${TF_SERVICE_ACCOUNT}" --role="roles/billing.costsManager" --configuration=ai-experiments
```

Never create or download a service-account credential file. Terraform access is keyless and uses
impersonation only.

## 5. Create the protected remote-state bucket

The committed lifecycle policy retains at least ten newer noncurrent versions and deletes an old
noncurrent version only after 30 days:

```bash
gcloud storage buckets create "gs://${STATE_BUCKET}" --location=asia-southeast1 --uniform-bucket-level-access --public-access-prevention --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud storage buckets update "gs://${STATE_BUCKET}" --versioning --lifecycle-file=infra/gcp/state-lifecycle.json --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud storage buckets add-iam-policy-binding "gs://${STATE_BUCKET}" --member="serviceAccount:${TF_SERVICE_ACCOUNT}" --role="roles/storage.admin" --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud storage buckets describe "gs://${STATE_BUCKET}" --project="${PROJECT_ID}" --configuration=ai-experiments
gcloud storage buckets get-iam-policy "gs://${STATE_BUCKET}" --project="${PROJECT_ID}" --configuration=ai-experiments
```

The state-bucket IAM grant must be applied to this bucket resource only. Verify location
`ASIA-SOUTHEAST1`, uniform bucket-level access, enforced public access prevention, versioning, the
committed lifecycle rule, and the exact service-account member before continuing.

## 6. Establish and verify keyless ADC

Create Application Default Credentials by impersonating the Terraform service account, replace
the prior quota-project association, and prove that a token can be minted without printing it:

```bash
gcloud auth application-default login \
  --impersonate-service-account="terraform-ai-experiments@${PROJECT_ID}.iam.gserviceaccount.com" \
  --configuration=ai-experiments
gcloud auth application-default set-quota-project "${PROJECT_ID}" \
  --configuration=ai-experiments
gcloud auth application-default print-access-token \
  --configuration=ai-experiments >/dev/null
```

Verify only the impersonation URL and credential type. The following check prints neither tokens
nor source credentials:

```bash
ADC_FILE="${CLOUDSDK_CONFIG:-${HOME}/.config/gcloud}/application_default_credentials.json"
EXPECTED_IMPERSONATION_URL="https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${TF_SERVICE_ACCOUNT}:generateAccessToken"
jq -e --arg expected "${EXPECTED_IMPERSONATION_URL}" \
  '.type == "impersonated_service_account" and .service_account_impersonation_url == $expected' \
  "${ADC_FILE}" >/dev/null
```

Stop if the check fails. Do not print, copy into the ledger, or commit the ADC JSON.

Copy `infra/gcp/project.env.example` to `infra/gcp/project.env`, then replace every project-derived
value with the reviewed literal values. The file must contain no quotes, `export` statements,
shell expansions, placeholders, or secrets. In particular, update all three of
`GCP_PROJECT_ID`, `GCP_TERRAFORM_SERVICE_ACCOUNT`, and `GCP_STATE_BUCKET` together.

Run the repository's fail-closed target guard:

```bash
uv run python -m shared.gcp.config --file infra/gcp/project.env --check-gcloud
```

Expected: `target verified: PROJECT_ID`. A mismatch is a hard stop. This verification does not
authorize a Terraform plan or apply; those are separate reviewed tasks.

## 7. Recover from a partial bootstrap

After any error, capture the exact command, exit status, output, and timestamp. Do **not**
automatically delete the project, unlink billing, remove the state bucket, remove IAM bindings, or
destroy a Terraform workspace. Diagnose with the corresponding read-only command, record every
resource that already exists, and resume idempotently from the first incomplete stage after user
review.

| Stage | Read-only diagnosis |
|---|---|
| Isolated configuration and account | `gcloud config list --configuration=ai-experiments` and `gcloud auth list --configuration=ai-experiments` |
| Organization discovery | `gcloud organizations list --configuration=ai-experiments` |
| Folder discovery | `gcloud resource-manager folders list --organization="ORGANIZATION_NUMBER" --configuration=ai-experiments` (or the confirmed `--folder`) |
| Billing discovery | `gcloud billing accounts list --filter="open=true" --configuration=ai-experiments` |
| Project discovery | `gcloud projects list --configuration=ai-experiments` |
| Project create | `gcloud projects describe "${PROJECT_ID}" --project="${PROJECT_ID}" --configuration=ai-experiments` |
| Billing link | `gcloud billing projects describe "${PROJECT_ID}" --project="${PROJECT_ID}" --configuration=ai-experiments` |
| API enablement | `gcloud services list --enabled --project="${PROJECT_ID}" --configuration=ai-experiments` |
| Terraform identity | `gcloud iam service-accounts describe "${TF_SERVICE_ACCOUNT}" --project="${PROJECT_ID}" --configuration=ai-experiments` |
| User impersonation grant | `gcloud iam service-accounts get-iam-policy "${TF_SERVICE_ACCOUNT}" --project="${PROJECT_ID}" --configuration=ai-experiments` |
| Project role grants | `gcloud projects get-iam-policy "${PROJECT_ID}" --project="${PROJECT_ID}" --configuration=ai-experiments` |
| Billing role grant | `gcloud billing accounts get-iam-policy "${BILLING_ACCOUNT_ID}" --configuration=ai-experiments` |
| State bucket settings | `gcloud storage buckets describe "gs://${STATE_BUCKET}" --project="${PROJECT_ID}" --configuration=ai-experiments` |
| State bucket IAM | `gcloud storage buckets get-iam-policy "gs://${STATE_BUCKET}" --project="${PROJECT_ID}" --configuration=ai-experiments` |
| Impersonated ADC | Run the non-printing `jq -e` URL/type check above, then the repository target guard. |

Specific recovery rules:

- A timeout or interrupted create is an unknown outcome: describe first, then either resume the
  existing owned project or retry only after confirming it does not exist.
- Re-running API enablement and additive IAM binding commands is acceptable only after inspection
  confirms the target identifiers and existing policy. Never replace a complete IAM policy.
- If the billing link names an unexpected account, stop for diagnosis; do not unlink it or link a
  different account automatically.
- If the state bucket exists, verify its project, ownership, location, access controls, versioning,
  lifecycle, and IAM. Do not delete or recreate it automatically.
- If ADC verification fails, leave cloud resources in place, fix the local impersonation setup,
  and rerun the non-printing checks.

The persistent project, billing link, identity, and state bucket are intentionally recovered by
fixing forward. Destructive cleanup requires a separate, ownership-aware plan and explicit user
approval.
