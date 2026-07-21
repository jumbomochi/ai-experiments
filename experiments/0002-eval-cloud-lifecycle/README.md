# 0002-eval-cloud-lifecycle

**Area:** `eval` · **Status:** running · **Started:** 2026-07-18

## Hypothesis

The eval runner can reach sovereign GCP inference and judge services only through local
SSH tunnels, preserve a complete cost and judgement trail in Postgres, and automatically
destroy each Terraform workspace when its campaign reaches a terminal state.

The operational lifecycle is successful only if both smoke campaigns finish and the final
inventory proves that the recovery created no remaining instances, disks, reserved
addresses, or buckets.

## Setup

- **Experiment ID:** `0002-eval-cloud-lifecycle`
- **Deterministic fixture:** `exact.jsonl`, released as immutable gold-set version
  `cloud-smoke-v0.0` at fixture commit marker `fixture-cloud-v0`
- **Rubric fixture:** `rubric.jsonl`, released as immutable gold-set version
  `judge-smoke-v0.0` at fixture commit marker `fixture-judge-v0`
- **Prompt template:** `prompt_templates/general/qa.j2`
- **L4 system under test:** `Qwen/Qwen2.5-7B-Instruct` from the committed L4 manifest,
  reached through `http://127.0.0.1:8000/v1`
- **Rubric system under test:** local `qwen2.5:0.5b-instruct` inference, judged by
  `Qwen/Qwen2.5-72B-Instruct-AWQ` through `http://127.0.0.1:8001/v1` and judge bundle
  `v0.2`
- **Disposable workspaces:** `infra/gcp/` for L4 inference and `infra/gcp/judge/` for
  the A100 judge
- **Persistence:** the production Postgres database retains the run, result, judgement,
  cost, and teardown evidence; no model-cache bucket is retained

Both endpoint URLs are loopback addresses by design. The services must not be exposed by a
public inference or judge firewall rule, and no ephemeral instance address belongs in a
committed manifest or judge bundle.

## Method

1. Load `exact.jsonl` as `cloud-smoke-v0.0` and `rubric.jsonl` as
   `judge-smoke-v0.0` through `shared.goldsets.loader.load_jsonl_to_postgres`.
2. Provision only the L4 workspace, establish its SSH local-forwarding tunnel, and record
   successful health through port 8000 before starting the deterministic campaign.
3. Run the one-example L4 campaign with experiment ID
   `0002-eval-cloud-lifecycle`, the deterministic judge bundle, the checked-in template
   root, and `infra/gcp/` supplied as the Terraform workspace.
4. Allow the runner's terminal-path teardown hook to destroy the L4 workspace. Record its
   teardown receipt and then independently inventory instances, disks, reserved addresses,
   and buckets.
5. Only after the L4 gate is clean, provision the A100 judge workspace, establish its SSH
   local-forwarding tunnel, and record successful health through port 8001. Keep the model
   under test on the Mac and route only rubric judging to the A100 endpoint.
6. Run the one-example rubric campaign with judge bundle `v0.2`, experiment ID
   `0002-eval-cloud-lifecycle`, the checked-in template root, and `infra/gcp/judge/`
   supplied as the Terraform workspace.
7. Allow the runner's terminal-path teardown hook to destroy the judge workspace. Record
   its teardown receipt and repeat the independent inventory.

**Cleanup is mandatory on success, budget halt, inference error, judge error, or operator
interruption.** At every failed provisioning or health gate, destroy the workspace just
created before diagnosis. Do not fall back to A3/H100 or non-preemptible capacity. A run is
not accepted until the teardown receipt succeeds and the post-destroy inventory is empty.

## Acceptance criteria

### Deterministic L4 gate

- Health succeeds through the SSH tunnel at `127.0.0.1:8000`, and the committed L4
  manifest names that tunnel endpoint.
- Postgres contains one completed run for `cloud-smoke-v0.0`, one result, and one
  deterministic judgement, with zero errored examples.
- The response to `ex_general_cloud0001` normalizes to `4` and receives score `1.0`.
- The run records `max_cost_usd`, `cost_actual_usd`, and `wall_seconds`; its result records
  `cost_increment_usd` and `wall_ms`.
- `run.notes` contains a `teardown_receipt` with `target`, `action`, `reason`, `workspace`,
  `success`, `returncode`, `stdout`, `stderr`, and `elapsed_ms`; acceptance requires
  `success: true` and `returncode: 0`.
- The post-destroy inventory contains no recovery-created instances, disks, reserved
  addresses, or buckets.

### Rubric A100 judge gate

- Health succeeds through the SSH tunnel at `127.0.0.1:8001`, and judge bundle `v0.2`
  names that tunnel endpoint.
- Postgres contains one completed run for `judge-smoke-v0.0`, one result, and one
  `lm_judge` judgement, with zero errored examples.
- The judgement has a numeric rubric score, no parse error, and a preserved raw response
  and rationale trace. The score is interpreted against the fixture's explicit `1.0`,
  `0.5`, and `0.0` rubric, not as a separate model-quality gate.
- The run records `max_cost_usd`, `cost_actual_usd`, and `wall_seconds`; its result records
  `cost_increment_usd` and `wall_ms`; its A100 judgement records
  `cost_increment_usd` separately from the model-under-test campaign cost.
- `run.notes` contains a `teardown_receipt` with `target`, `action`, `reason`, `workspace`,
  `success`, `returncode`, `stdout`, `stderr`, and `elapsed_ms`; acceptance requires
  `success: true` and `returncode: 0`.
- The post-destroy inventory contains no recovery-created instances, disks, reserved
  addresses, or buckets.

## Results

Status: not yet run

No live campaign identifiers, measured costs, teardown receipts, or cloud inventory
evidence have been recorded. Populate this section only from the live L4 and A100 judge
runs and their post-destroy inventory commands.

## Conclusion

Pending both live operational gates. The hypothesis is neither supported nor rejected
until the required run, cost, teardown, and empty-inventory evidence is preserved here.
