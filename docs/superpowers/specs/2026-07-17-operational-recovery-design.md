# Operational Recovery and Phase-Gate Design

**Date:** 2026-07-17
**Status:** Approved

## Context

The repository has a tested Mac evaluation substrate and Sprint 2 scaffolding for GCP,
Argilla, and rubric-based LLM judging. Operational state has not caught up with that code:
the project database contains only the three-example Mac smoke set, cloud endpoints remain
placeholders, no `v0.1` gold-set artifacts exist, automatic cloud teardown is a no-op, and
the planning documents still describe Phase 2 and Phase 3 as planned.

This recovery is intentionally staged. Each tranche must leave the repository and external
infrastructure in a coherent state even if a later tranche is blocked by quota, capacity,
model startup, or human-review constraints.

The active GCP project is `adept-prod-497323`. A read-only inventory on 2026-07-15 found no
GCE instances, persistent disks, reserved addresses, or GCS buckets. Resources created by
this recovery are therefore distinguishable from pre-existing resources and must be destroyed
before the execution session ends.

## Goals

1. Restore a truthful, lint-clean repository baseline with current execution status recorded.
2. Make teardown a tested part of the campaign lifecycle rather than an operator convention.
3. Validate one deterministic cloud campaign and one rubric-judge campaign through private
   SSH tunnels, with actual run records and cost receipts.
4. Destroy every paid GCP resource created by the smoke tests, whether the tests pass or fail.
5. Start gold-set production with a reviewed general lane before expanding to other lanes.
6. Defer judge calibration until enough reviewed rubric examples exist to support it.

## Non-goals

- Completing all 150 Sprint 2 examples in one unattended execution.
- Claiming human review, double annotation, Cohen's kappa, or bias calibration without people
  actually performing those steps.
- Falling back automatically to a more expensive GPU when A100 quota, capacity, or memory is
  insufficient.
- Retaining model-cache buckets or annotation databases created during the smoke tests.
- Starting Phase 4 lane-depth or Phase 5 memory work.

## Tranche 1: Repository Recovery

### Planning state

`ROADMAP.md`, `PLAN.md`, and `EXPERIMENTS.md` will be reconciled with observed state:

- Phase 1 remains `in progress` until cloud execution, replay, and automatic teardown pass.
- Phase 2 becomes `in progress`; Argilla is recorded as the selected annotation tool.
- Phase 3 becomes `in progress` only at the generalist-judge integration level. Specialist
  selection, human calibration, kappa gates, and bias tests remain open.
- The July 26 Phase 2 release target is replaced by dependency-based gates rather than another
  speculative date.
- Actual experiment folders and experiment identifiers become canonical; roadmap references
  must not reuse an identifier for a different experiment.
- A dated slip/rebaseline note records the difference between software scaffolding and live
  operational evidence.

### Engineering baseline

The eight existing Ruff findings are fixed without changing behavior. The gate for this tranche
is a fresh full test run and a clean full Ruff run.

The Mac smoke experiment is rerun after migration 002. Its run, result, and judgement rows remain
in the development database so replay can be exercised against current schema rather than only
documented from the deleted May run.

## Tranche 2: Safe Cloud Campaign Lifecycle

### Terraform teardown hook

Add `TerraformTeardownHook` under `shared/eval/runner/teardown.py`.

The hook:

- accepts an explicit Terraform workspace path;
- verifies that the path is a directory containing Terraform configuration;
- invokes a fixed argument vector, never a shell string:
  `terraform destroy -auto-approve -input=false`;
- captures exit code, bounded stdout, bounded stderr, workspace, action, reason, and elapsed time;
- returns a JSON-serializable receipt;
- treats a second destroy as safe and idempotent;
- never claims success when Terraform exits non-zero or the binary/workspace is missing.

`run_campaign` retains explicit hook injection for tests and advanced callers. The CLI gains an
explicit `--terraform-workspace` option. A manifest whose `target_host` starts with
`cloud-burst-` is rejected before inference unless an explicit teardown hook or workspace is
present. Local Mac and Spark targets continue to use `LocalTeardownHook`.

All DB-writable terminal paths use the same teardown-and-finalize helper. A failed cleanup changes
the terminal status to `halted_teardown_failed`; the run error preserves the pre-teardown status
and error, and the teardown receipt is stored in `run.notes`. If PostgreSQL is unavailable, the
hook still executes before the original database failure is re-raised, although no receipt can be
persisted.

### Network exposure

The current public firewall rules for ports 8000 and 6900 are removed before any apply. Services
bind on their VM as before but are reached from the Mac through SSH local forwarding:

- eval model: `127.0.0.1:8000` -> eval VM `127.0.0.1:8000`;
- judge model: `127.0.0.1:8001` -> judge VM `127.0.0.1:8000`;
- Argilla: `127.0.0.1:6900` -> annotation VM `127.0.0.1:6900`.

Static external addresses are removed. Terraform outputs the instance names needed by `gcloud
compute ssh`; ephemeral external addresses are sufficient for SSH. Make targets start the tunnels
and health checks target the local forwarded ports.

The checked-in model manifests and judge bundle use the stable local tunnel endpoints, eliminating
IP placeholders without committing ephemeral infrastructure details.

### Disposable cloud state

The recovery workspaces do not create or reference a GCS model-cache bucket. Startup scripts
download model weights directly to each instance's auto-deleted boot disk. This sacrifices warm
cache reuse in exchange for independent workspaces and the explicitly requested zero-residual-
resource outcome. A persistent cache can be designed later as a separately owned resource with an
explicit retention decision.

Provisioning order is:

1. Eval L4 workspace up; tunnel; deterministic smoke campaign; automatic eval-workspace destroy.
2. Judge A100 workspace up; judge tunnel; rubric smoke campaign using the Mac model as the system
   under test; automatic judge-workspace destroy.

At every failed gate, destroy the workspace just created before diagnosing further. No automatic
upgrade to A3/H100 or a non-preemptible GPU is allowed. Quota or capacity failure is recorded as a
blocker, not worked around with additional spend.

### Operational evidence

A cloud smoke is accepted only when all of the following are recorded:

- endpoint health through the SSH tunnel;
- a completed Postgres `run` with `result` and `judgement` rows;
- the committed manifest and judge bundle match the tunnel endpoints used;
- cost and teardown receipt are present on the run;
- post-destroy inventory shows no instances, disks, reserved addresses, or buckets created by the
  recovery.

Mocked integration tests remain useful but cannot satisfy this gate.

## Tranche 3: Gold-Set Curation and Judge Calibration

### General lane first

The general lane advances from two stubs to forty candidate seeds. Candidate creation and review
are separate states: generated or drafted inputs are not counted as gold examples until an
annotator submits an expected answer or rubric and a second check confirms it.

Argilla is provisioned only for an annotation session, accessed through the SSH tunnel, and
exported to local `annotated.jsonl` before teardown. The session flow is:

`validate-seed -> push -> annotate -> review -> export -> test-load -> dev-load -> destroy`

The first acceptance slice is ten reviewed general examples, including at least two rubric examples,
because this is enough to exercise the complete curation and judge path without pretending the
forty-example lane is finished. The lane expands to forty through repeated reviewed slices.

### Remaining lanes

SEA, Japanese, finance, and OCR/VLM begin only after the general-lane slice passes. Each lane follows
the targets and quality gates in the approved Sprint 2 curation specification. Seed counts, submitted
counts, reviewed counts, and released counts are reported separately.

### Calibration gate

Specialist-judge selection, the 100-200-example double-annotated calibration set, Cohen's kappa,
strict trust enforcement, and bias stress tests begin only after reviewed rubric examples exist.
Until then, judge bundle v0.2 remains `trust.enforcement: lenient` and must not be described as
production-calibrated.

## Error Handling and Cleanup

- Every cloud apply is paired with a destroy in the same execution scope.
- Interruptions and failed health checks enter cleanup before returning control.
- Terraform destroy failures are surfaced as first-class failures and followed by direct GCP
  inventory checks; resources are never assumed gone from command intent alone.
- No pre-existing resource may be deleted. The initial empty inventory is captured in the recovery
  notes and compared with the final inventory.
- Annotation export must complete before destroying the annotation VM. If export fails, preserve
  the VM only long enough to retry or recover data, then destroy it before ending the session.

## Testing and Verification

Behavior changes follow red-green-refactor:

- unit tests for successful, failed, missing-binary, invalid-workspace, and idempotent Terraform
  teardown;
- runner tests for cloud-workspace enforcement, cleanup on setup failure, cleanup on budget halt,
  cleanup on success, and `halted_teardown_failed` status;
- CLI parsing tests for `--terraform-workspace`;
- Terraform formatting and `terraform validate` for all three workspaces;
- full `pytest` and Ruff gates after each code tranche;
- live Mac smoke and replay queries;
- live cloud health, campaign, teardown, and final inventory evidence.

Terraform configuration changes are verified with `terraform fmt -check` and `terraform validate`;
they do not add Python behavior and therefore do not require Python unit tests.

## Deliverables and Phase Gates

The work produces separate implementation plans so each tranche is reviewable and executable on
its own:

1. repository recovery and current-state reconciliation;
2. Terraform teardown plus private-tunnel cloud smoke;
3. general-lane curation slice and calibration entry criteria.

Phase 1 completes only after Tranches 1 and 2 pass and its documentation milestone is published.
Phase 2 remains in progress until every lane meets its release target and `v0.1` is tagged. Phase 3
remains in progress until calibration and bias gates pass.
