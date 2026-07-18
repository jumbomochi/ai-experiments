# Operational rebaseline — 2026-07-18

## Why this exists

The calendar advanced from Sprint 1 to Sprint 3 while operational evidence did not. Code scaffolding for GCP inference, Argilla, and rubric judging landed, but the development database still contained only the three-example Mac smoke set and no current run rows. This note separates implemented software from exercised capability.

## Observed baseline

- Repository: clean `main`; no open pull requests, issues, release tags, or additional branches at the 2026-07-14 catch-up.
- Tests: 102 passed on 2026-07-14; Ruff had eight cleanup findings before Tranche 1.
- Development DB: migrations 001 and 002 applied; one Mac manifest; judge bundle v0.1; smoke-v0.0 with three examples; zero preserved runs after migration 002 truncated development data.
- Gold sets: two candidate seeds in each of five lanes; no annotated JSONL and no v0.1 tag.
- GCP inventory: no instances, persistent disks, reserved addresses, or buckets in `adept-prod-497323` when checked on 2026-07-15.
- Cloud configuration: L4, A100 judge, and Argilla Terraform workspaces exist but have not been validated live; model and judge endpoints still require the private-tunnel recovery changes.

## Decision

Execution is dependency-gated rather than date-gated: restore the repository baseline, prove private cloud execution and teardown, complete a reviewed ten-example general slice, then expand lanes and begin calibration. Phase 4 and memory work remain paused.

## What counts as progress

Generated candidates, mocked tests, Terraform files, and elapsed sprint dates are reported separately from reviewed examples, live campaigns, destroyed infrastructure, and calibrated judges. Only the latter satisfy phase acceptance gates.
