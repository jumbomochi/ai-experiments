# GCP Project Bootstrap and Budget Controls Design

**Date:** 2026-07-22
**Status:** Approved — native SGD amendment confirmed

## Context

The operational-recovery work incorrectly treated the active local gcloud configuration as
the cloud target for this repository. That configuration was named `adept`, used
`huiliang@gmail.com`, and targeted `adept-prod-497323`, which belongs to another project.
The repository originally contained only the placeholder `your-gcp-project-id`; the Adept
identifier entered the recovery design and plans through this incorrect inference.

No GCP resources were created by the failed recovery attempts. The final inventories for
instances, disks, reserved addresses, and buckets in the Adept project were empty, and the
local Terraform state contained no resources. Cloud execution is stopped until this design
is implemented.

This repository must instead use `huiliang@sgcodecampus.com` to create and administer a
dedicated Google Cloud project. The project needs reproducible, keyless Terraform access and
project-scoped cost controls before any GPU campaign resumes.

## Decisions

- Google account: `huiliang@sgcodecampus.com`.
- Project display name: `AI Experiments`.
- Preferred project ID: `sgcc-ai-experiments`; if unavailable, append a short stable suffix
  and record the resulting ID as the repository's canonical target.
- Authentication: user bootstrap followed by keyless service-account impersonation; no
  downloaded service-account keys.
- Monthly project budget: SGD 100.
- Current-spend alerts: SGD 10, SGD 50, and SGD 100.
- At or above SGD 100: automatically stop running Compute Engine instances in this project.
- Do not automatically disable billing or delete disks, buckets, or the project.
- Keep project controls persistent and campaign compute disposable in separate Terraform
  states.

The selected self-serve Cloud Billing account uses Singapore as its country and SGD as its fixed
currency. Setup stops before budget creation if the resulting billing account currency is not
exactly SGD.

## Considered Approaches

### Two-stage bootstrap plus Terraform-managed controls — selected

Use the administrator's user credentials only to discover the organization/folder and billing
account, create and link the project, create the Terraform identity, and establish remote
state. Terraform then impersonates the dedicated service account and manages project APIs,
IAM, budgets, notification infrastructure, and disposable workloads.

This approach is reproducible, avoids persistent keys, and keeps the one-time privilege bridge
small and auditable.

### All gcloud commands

This is faster for the first setup but leaves IAM, budgets, and shutdown automation vulnerable
to drift and makes review or recreation difficult.

### Organization-level Terraform bootstrap

This is appropriate when an organization already has an administrative Terraform identity,
state backend, and landing-zone modules. Creating that broader platform solely for this project
would expand scope without improving the immediate safety gate.

## Architecture

### 1. Explicit gcloud configuration

Create a gcloud configuration named `ai-experiments`. Every bootstrap and diagnostic command
uses `--configuration=ai-experiments`; every resource command also uses an explicit project ID.
The existing `adept` configuration is never activated, modified, or used by this repository.

The bootstrap flow authenticates `huiliang@sgcodecampus.com`, then lists the organizations,
folders, projects, and billing accounts visible to that identity. If more than one plausible
organization/folder or billing account is available, execution stops for a user selection.
It does not infer ownership from whichever gcloud configuration happens to be active.

### 2. Project bootstrap

Using the authenticated administrator identity:

1. Verify that the preferred project ID is available; otherwise select and record a short
   suffixed ID.
2. Create the project under the confirmed organization or folder.
3. Link the confirmed Cloud Billing account.
4. Enable only the APIs needed for IAM, Service Usage, Cloud Billing budgets, Pub/Sub,
   Cloud Run functions, Eventarc, Cloud Build/Artifact Registry, Storage, Logging, Monitoring,
   and Compute Engine.
5. Create `terraform-ai-experiments@<project-id>.iam.gserviceaccount.com`.
6. Grant `huiliang@sgcodecampus.com` permission to impersonate that service account.
7. Grant the service account only the project and billing-account permissions required by the
   Terraform resources in this design. Do not grant Owner and do not create a key.

Project creation and billing linkage remain explicit bootstrap operations because the
project-scoped Terraform identity cannot exist before the project does.

### 3. Keyless Terraform authentication

After the service account and impersonation binding exist, create local Application Default
Credentials through service-account impersonation. Terraform must resolve to
`terraform-ai-experiments`, not directly to either user's credentials.

Verification records the principal returned by an impersonated token test and runs a read-only
Terraform validation before any apply. The prior Adept ADC quota-project association is replaced
as part of this authentication setup.

### 4. Remote state and workspace separation

Create one Singapore-region GCS state bucket named from the canonical project ID. Configure:

- uniform bucket-level access;
- public access prevention;
- object versioning;
- lifecycle cleanup for old noncurrent state versions;
- bucket-scoped access for the Terraform service account.

Each Terraform workspace uses a separate state prefix:

- `project-controls/` — APIs, IAM, budget, Pub/Sub, and shutdown function;
- `eval-l4/` — disposable L4 inference resources;
- `judge-a100/` — disposable judge resources;
- `annotation/` — annotation workspace when explicitly started.

The runner's automatic destroy hook can therefore destroy a campaign workspace without touching
the project, budget, shutdown automation, or state bucket. Existing local eval state is empty
and is discarded only after another empty-inventory verification.

## Budget Controls

### Project-scoped budget

Terraform creates one `google_billing_budget` scoped to the new project's numeric project ID.
The specified amount is SGD 100 per calendar month. Current-spend threshold rules are:

- `0.10` — SGD 10;
- `0.50` — SGD 50;
- `1.00` — SGD 100.

Project-level recipients are enabled so project owners receive threshold email. The budget also
publishes spend updates to a dedicated Pub/Sub topic. Budget deletion protection is enabled so a
routine Terraform destroy cannot silently remove the cost guardrail.

Cloud Billing budget data is estimated and notifications are not real-time. The budget is a
safety backstop, not a guarantee that invoiced cost stops at exactly SGD 100.

### Automatic Compute shutdown

A second-generation Cloud Run function in `asia-southeast1` subscribes to the budget Pub/Sub
topic. Its dedicated runtime service account receives a project-level custom role containing
only the permissions needed to list, inspect, and stop Compute Engine instances and to write
logs.

For each notification, the function:

1. Validates the expected budget display name and target project.
2. Parses `costAmount` and `budgetAmount` defensively.
3. Returns without mutation when spend is below the budget.
4. At or above 100%, lists running Compute Engine instances across all project zones.
5. Stops each running instance and records structured success or failure logs.

The handler is idempotent. Duplicate or out-of-order Pub/Sub delivery cannot restart instances,
and attempting to stop an already-stopped instance has no destructive effect. The function does
not detach billing, delete resources, or operate outside the dedicated project.

## Repository Configuration

After project creation, commit one non-secret canonical environment file under `infra/gcp/`
containing the gcloud configuration name, actual project ID, region, and zone. Makefiles and
documented commands load this file and reject a missing or mismatched configuration.

Replace every active-target `adept-prod-497323` reference in the prior recovery design, plans,
notes, and ignored runtime configuration. Preserve a clearly marked historical incident record
that the wrong target was identified and created zero resources, but ensure no executable
example or current instruction continues to point at Adept.

Secrets such as Hugging Face tokens remain environment inputs and never enter the canonical
project file, Terraform variables committed to Git, Terraform state output, or logs.

## Error Handling and Stop Conditions

Bootstrap stops without creating or mutating cloud resources when:

- the authenticated account is not exactly `huiliang@sgcodecampus.com`;
- organization/folder or billing-account selection is ambiguous;
- the chosen billing account cannot be linked by the authenticated user;
- the billing account currency is not SGD;
- the project ID selection is not recorded consistently;
- impersonation does not resolve to the dedicated Terraform service account;
- any required API, IAM binding, budget resource, or notification component fails validation.

After project creation, any partial bootstrap failure records the resources that exist and avoids
blind deletion of the project or billing link. Cleanup is explicit and ownership-aware.

Disposable campaign applies retain the existing rule: on any failure, destroy that campaign's
Terraform workspace and verify instances, disks, addresses, and campaign buckets are empty.

## Verification

### Static and unit verification

- Terraform formatting and validation for the bootstrap/project-controls and all campaign
  workspaces.
- Tests for budget messages below, exactly at, and above the threshold.
- Tests for malformed messages, unrelated budget names/projects, duplicate delivery, partial
  stop failures, and already-stopped instances.
- Tests that assert the shutdown identity cannot target another project.
- Repository scan proving no executable or current planning instruction still targets
  `adept-prod-497323`; explicitly historical incident text is allowed.

### Live project-control verification

Before any GPU workload:

1. Confirm the canonical gcloud configuration, user, project, organization/folder, and billing
   account.
2. Confirm Terraform is impersonating `terraform-ai-experiments`.
3. Confirm the SGD 100 project budget and 10%, 50%, and 100% thresholds.
4. Confirm the Pub/Sub topic and Cloud Run function are healthy.
5. Create a temporary inexpensive `e2-micro` VM with an auto-delete boot disk.
6. Publish a synthetic 100% budget notification matching the configured budget and project.
7. Verify the function stops the VM and emits a successful structured log.
8. Destroy the VM and verify its disk is gone.
9. Verify no disposable instances, disks, reserved addresses, or campaign buckets remain.

Only after this gate passes may the L4 and A100 smoke campaigns resume.

## Persistent and Disposable Resources

The following resources intentionally persist as the project's safety control plane:

- the project and billing link;
- the Terraform and shutdown service accounts and IAM bindings;
- the Terraform state bucket;
- enabled APIs;
- the project budget;
- the Pub/Sub topic and budget notification binding;
- the Cloud Run shutdown function and its deployment artifacts.

GPU instances, test VMs, their auto-delete disks, temporary addresses, and campaign-specific
artifacts are disposable and must be destroyed after their verification tasks.

## Completion Gate

This design is complete when the new project is explicitly identified, authentication is
keyless and verified, Terraform state is remote and separated, the budget and email thresholds
exist, the synthetic shutdown test passes, active Adept targeting is removed, and the disposable
resource inventory is empty. GPU campaign execution remains blocked until every condition is
met.

## References

- [Authentication for Terraform](https://docs.cloud.google.com/docs/terraform/authentication)
- [Application Default Credentials](https://docs.cloud.google.com/docs/authentication/application-default-credentials)
- [Create and manage Cloud Billing budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets)
- [Programmatic budget notifications](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications)
- [Control resource usage with notifications](https://docs.cloud.google.com/billing/docs/how-to/control-usage)
- [Terraform `google_billing_budget`](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/billing_budget)
