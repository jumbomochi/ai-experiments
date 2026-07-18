# Tranche 2 Safe Cloud Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove private-tunnel GCP inference and rubric judging while making Terraform destruction a tested, recorded campaign terminal action.

**Architecture:** A shell-free `TerraformTeardownHook` owns one explicit Terraform workspace and returns a bounded JSON receipt. The runner funnels every DB-writable exit through one teardown/finalization helper and refuses cloud manifests without explicit cleanup ownership. Terraform workspaces expose services only through SSH local forwarding, use ephemeral boot disks and IPs, download models directly, and leave no cache bucket or paid resource behind.

**Tech Stack:** Python 3.12, pytest, PostgreSQL 17, Terraform with Google provider `~> 5.0`, GCE L4 and A100, vLLM, gcloud CLI, SSH local forwarding, Make.

## Global Constraints

- Follow red-green-refactor for every Python behavior change.
- Never invoke Terraform through `shell=True` or a shell string.
- `TerraformTeardownHook` executes exactly `terraform destroy -auto-approve -input=false` in an explicit workspace.
- A `cloud-burst-*` manifest cannot begin inference without an explicit hook or `terraform_workspace`.
- A teardown failure produces terminal status `halted_teardown_failed` and preserves the prior status/error.
- Ports 8000 and 6900 must not have GCP firewall rules; access is by SSH tunnel only.
- Do not create static external addresses or GCS buckets.
- Do not upgrade automatically to A3/H100, non-preemptible GPU, or another region.
- Destroy resources after every successful or failed live campaign and verify deletion through GCP inventory.
- The L4 campaign uses the L4 workspace; the rubric campaign uses the Mac model plus the A100 judge workspace.

---

### Task 1: Implement the Terraform teardown receipt

**Files:**
- Create: `tests/shared/eval/test_teardown.py`
- Modify: `shared/eval/runner/teardown.py`

**Interfaces:**
- Consumes: `pathlib.Path` workspace and a subprocess-compatible runner.
- Produces: `TerraformTeardownHook(workspace: Path, *, runner=subprocess.run, terraform_binary: str = "terraform")` implementing `teardown(reason: str) -> dict[str, object]`.
- Produces receipt keys: `target`, `action`, `reason`, `workspace`, `success`, `returncode`, `stdout`, `stderr`, `elapsed_ms`.

- [ ] **Step 1: Write failing teardown tests**

Create `tests/shared/eval/test_teardown.py`:

```python
"""Unit tests for local and Terraform teardown hooks."""
from __future__ import annotations

import subprocess
from pathlib import Path

from shared.eval.runner.teardown import LocalTeardownHook, TerraformTeardownHook


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "infra"
    workspace.mkdir()
    (workspace / "main.tf").write_text("terraform {}\n")
    return workspace


def test_local_teardown_receipt_is_successful() -> None:
    receipt = LocalTeardownHook().teardown("completed")
    assert receipt == {
        "target": "local",
        "action": "noop",
        "reason": "completed",
        "success": True,
    }


def test_terraform_teardown_runs_fixed_argv_in_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    calls: list[tuple[list[str], Path]] = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs["cwd"]))
        assert kwargs["shell"] is False
        return subprocess.CompletedProcess(argv, 0, "destroyed", "")

    receipt = TerraformTeardownHook(workspace, runner=runner).teardown("budget")

    assert calls == [
        (["terraform", "destroy", "-auto-approve", "-input=false"], workspace.resolve())
    ]
    assert receipt["success"] is True
    assert receipt["returncode"] == 0
    assert receipt["stdout"] == "destroyed"


def test_terraform_teardown_reports_nonzero_exit(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "partial", "quota error")

    receipt = TerraformTeardownHook(workspace, runner=runner).teardown("failed")
    assert receipt["success"] is False
    assert receipt["returncode"] == 1
    assert receipt["stderr"] == "quota error"


def test_terraform_teardown_reports_missing_binary(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    def runner(argv, **kwargs):
        raise FileNotFoundError("terraform")

    receipt = TerraformTeardownHook(workspace, runner=runner).teardown("failed")
    assert receipt["success"] is False
    assert receipt["returncode"] is None
    assert "terraform binary not found" in receipt["stderr"]


def test_terraform_teardown_rejects_invalid_workspace(tmp_path: Path) -> None:
    receipt = TerraformTeardownHook(tmp_path / "missing").teardown("failed")
    assert receipt["success"] is False
    assert receipt["returncode"] is None
    assert "workspace is not a directory" in receipt["stderr"]


def test_terraform_teardown_rejects_directory_without_tf(tmp_path: Path) -> None:
    workspace = tmp_path / "empty"
    workspace.mkdir()
    receipt = TerraformTeardownHook(workspace).teardown("failed")
    assert receipt["success"] is False
    assert "contains no .tf files" in receipt["stderr"]


def test_terraform_teardown_is_idempotent(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    calls = 0

    def runner(argv, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(argv, 0, "No changes", "")

    hook = TerraformTeardownHook(workspace, runner=runner)
    assert hook.teardown("first")["success"] is True
    assert hook.teardown("second")["success"] is True
    assert calls == 2


def test_terraform_teardown_bounds_captured_output(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, "x" * 10_000, "y" * 10_000)

    receipt = TerraformTeardownHook(workspace, runner=runner).teardown("done")
    assert len(receipt["stdout"]) == 4_000
    assert len(receipt["stderr"]) == 4_000
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
uv run pytest tests/shared/eval/test_teardown.py -v
```

Expected: collection fails because `TerraformTeardownHook` does not exist, and the local receipt test fails because `success` is absent.

- [ ] **Step 3: Implement the minimal teardown hooks**

Replace `shared/eval/runner/teardown.py` with:

```python
"""Teardown hooks for always-on and Terraform-managed targets."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable, Protocol

_RECEIPT_TEXT_LIMIT = 4_000
Runner = Callable[..., subprocess.CompletedProcess[str]]


class TeardownHook(Protocol):
    def teardown(self, reason: str) -> dict[str, object]:
        """Tear down compute and return a JSON-serializable receipt."""
        ...


class LocalTeardownHook:
    """No-op teardown for always-on targets."""

    def teardown(self, reason: str) -> dict[str, object]:
        return {
            "target": "local",
            "action": "noop",
            "reason": reason,
            "success": True,
        }


class TerraformTeardownHook:
    """Destroy one explicit Terraform workspace without invoking a shell."""

    def __init__(
        self,
        workspace: Path,
        *,
        runner: Runner = subprocess.run,
        terraform_binary: str = "terraform",
    ) -> None:
        self.workspace = workspace.resolve()
        self._runner = runner
        self.terraform_binary = terraform_binary

    def teardown(self, reason: str) -> dict[str, object]:
        started = time.perf_counter()
        receipt: dict[str, object] = {
            "target": "terraform",
            "action": "destroy",
            "reason": reason,
            "workspace": str(self.workspace),
            "success": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }

        if not self.workspace.is_dir():
            receipt["stderr"] = "terraform workspace is not a directory"
            return self._finish(receipt, started)
        if not any(self.workspace.glob("*.tf")):
            receipt["stderr"] = "terraform workspace contains no .tf files"
            return self._finish(receipt, started)

        argv = [self.terraform_binary, "destroy", "-auto-approve", "-input=false"]
        try:
            completed = self._runner(
                argv,
                cwd=self.workspace,
                check=False,
                capture_output=True,
                text=True,
                shell=False,
            )
        except FileNotFoundError:
            receipt["stderr"] = f"terraform binary not found: {self.terraform_binary}"
            return self._finish(receipt, started)

        receipt.update(
            success=completed.returncode == 0,
            returncode=completed.returncode,
            stdout=(completed.stdout or "")[-_RECEIPT_TEXT_LIMIT:],
            stderr=(completed.stderr or "")[-_RECEIPT_TEXT_LIMIT:],
        )
        return self._finish(receipt, started)

    @staticmethod
    def _finish(receipt: dict[str, object], started: float) -> dict[str, object]:
        receipt["elapsed_ms"] = int((time.perf_counter() - started) * 1_000)
        return receipt
```

- [ ] **Step 4: Run the teardown tests to verify GREEN**

```bash
uv run pytest tests/shared/eval/test_teardown.py -v
```

Expected: 8 tests pass.

- [ ] **Step 5: Run Ruff on the new files**

```bash
uv run ruff check shared/eval/runner/teardown.py tests/shared/eval/test_teardown.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit the teardown primitive**

```bash
git add shared/eval/runner/teardown.py tests/shared/eval/test_teardown.py
git commit -m "feat: add recorded Terraform teardown hook"
```

---

### Task 2: Integrate teardown into every runner terminal path

**Files:**
- Modify: `shared/eval/runner/runner.py`
- Modify: `tests/integration/test_runner.py`

**Interfaces:**
- Consumes: `TerraformTeardownHook`, `LocalTeardownHook`, and optional `teardown_hook` injection.
- Produces: `run_campaign(..., terraform_workspace: Path | None = None)`.
- Produces: `_apply_teardown_outcome(status: str, error: dict | None, receipt: dict[str, object]) -> tuple[str, dict | None]`.
- Produces: `_finish_run(...) -> RunResult`, the only DB-writable teardown/finalization path.

- [ ] **Step 1: Add test helpers and failing lifecycle tests**

Append to `tests/integration/test_runner.py`:

```python
class _RecordingHook:
    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.reasons: list[str] = []

    def teardown(self, reason: str) -> dict[str, object]:
        self.reasons.append(reason)
        return {
            "target": "test",
            "action": "destroy",
            "reason": reason,
            "success": self.success,
            "returncode": 0 if self.success else 1,
        }


def _sync_cloud_manifest(tmp_path: Path) -> None:
    manifest_yaml = tmp_path / "cloud.yaml"
    manifest_yaml.write_text(
        'id: "test/cloud-model"\n'
        'family: test\nsize: 1b\nrevision: "main"\n'
        'runtime: vllm\nruntime_version: "0.4.3"\n'
        'target_host: cloud-burst-l4\nendpoint: "http://127.0.0.1:8000/v1"\n'
        'capabilities: [chat]\ncontext_window: 4096\n'
        'default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 8}\n'
    )
    sync_to_postgres([load_manifest_yaml(manifest_yaml)], test=True)


def test_success_calls_teardown_once_and_records_receipt(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text("{{ question }}")
    hook = _RecordingHook()

    with patch("shared.inference.client.InferenceClient.chat",
               return_value=_stub_inference_response("B")):
        rr = run_campaign(
            "qwen2.5:0.5b-instruct", "smoke-v0.0", "v0.1", 1.0,
            template_root, test=True, teardown_hook=hook,
        )

    assert rr.status == "completed"
    assert hook.reasons == ["run_finalize_completed"]
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT notes FROM run WHERE id=%s", (rr.run_id,))
        assert '"success": true' in cur.fetchone()[0]


def test_budget_halt_calls_teardown_once(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text("{{ question }}")
    hook = _RecordingHook()

    with patch("shared.inference.client.InferenceClient.chat",
               return_value=_stub_inference_response("B")):
        rr = run_campaign(
            "qwen2.5:0.5b-instruct", "smoke-v0.0", "v0.1", -1e-9,
            template_root, test=True, teardown_hook=hook,
        )

    assert rr.status == "halted_budget"
    assert hook.reasons == ["run_finalize_halted_budget"]


def test_setup_failure_calls_teardown_and_finalizes(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    hook = _RecordingHook()

    rr = run_campaign(
        "missing-model", "smoke-v0.0", "v0.1", 1.0, tmp_path,
        test=True, teardown_hook=hook,
    )

    assert rr.status == "halted_setup"
    assert hook.reasons == ["run_finalize_halted_setup"]
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT finished_at FROM run WHERE id=%s", (rr.run_id,))
        assert cur.fetchone()[0] is not None


def test_teardown_failure_changes_terminal_status(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text("{{ question }}")
    hook = _RecordingHook(success=False)

    with patch("shared.inference.client.InferenceClient.chat",
               return_value=_stub_inference_response("B")):
        rr = run_campaign(
            "qwen2.5:0.5b-instruct", "smoke-v0.0", "v0.1", 1.0,
            template_root, test=True, teardown_hook=hook,
        )

    assert rr.status == "halted_teardown_failed"
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT error FROM run WHERE id=%s", (rr.run_id,))
        error = cur.fetchone()[0]
    assert error["pre_teardown_status"] == "completed"
    assert error["teardown_receipt"]["success"] is False


def test_cloud_manifest_requires_cleanup_ownership(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    _sync_cloud_manifest(tmp_path)

    rr = run_campaign(
        "test/cloud-model", "smoke-v0.0", "v0.1", 1.0, tmp_path, test=True,
    )

    assert rr.status == "halted_setup"
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT error FROM run WHERE id=%s", (rr.run_id,))
        assert cur.fetchone()[0]["step"] == "teardown"


def test_postgres_preflight_failure_still_calls_teardown(tmp_path: Path) -> None:
    hook = _RecordingHook()
    failure = PreflightFailure("postgres", RuntimeError("db down"))

    with patch("shared.eval.runner.runner.preflight_or_raise", side_effect=failure):
        with pytest.raises(PreflightFailure, match="postgres"):
            run_campaign(
                "model", "version", "v0.1", 1.0, tmp_path,
                test=True, teardown_hook=hook,
            )

    assert hook.reasons == ["run_finalize_postgres_failure"]
```

Also add this import near the existing runner imports:

```python
from shared.eval.errors import PreflightFailure
```

- [ ] **Step 2: Run the new lifecycle tests to verify RED**

```bash
uv run pytest tests/integration/test_runner.py -k 'teardown or cleanup_ownership or setup_failure or postgres_preflight' -v
```

Expected: failures show missing finalization, missing cloud enforcement, and unchanged status after teardown failure.

- [ ] **Step 3: Add hook selection and cloud enforcement**

In `shared/eval/runner/runner.py`, import `TerraformTeardownHook` and extend the signature:

```python
from shared.eval.runner.teardown import (
    LocalTeardownHook,
    TeardownHook,
    TerraformTeardownHook,
)


def run_campaign(
    model_id: str,
    gold_set_version: str,
    judge_config_version: str,
    max_cost_usd: float,
    template_root: Path,
    experiment_id: str | None = None,
    test: bool = False,
    teardown_hook: TeardownHook | None = None,
    terraform_workspace: Path | None = None,
    inference_client_factory=None,
    judge_client_factory=None,
) -> RunResult:
    explicit_cleanup = teardown_hook is not None or terraform_workspace is not None
    if teardown_hook is None:
        teardown_hook = (
            TerraformTeardownHook(terraform_workspace)
            if terraform_workspace is not None
            else LocalTeardownHook()
        )
```

Immediately after successful preflight and before `_fetch_examples`, add:

```python
    if manifest.target_host.startswith("cloud-burst-") and not explicit_cleanup:
        failure = PreflightFailure(
            "teardown",
            RuntimeError(
                f"cloud target {manifest.target_host!r} requires teardown_hook "
                "or terraform_workspace"
            ),
        )
        _write_run_row(
            run_id=run_id,
            model_id=model_id,
            model_manifest=manifest.model_dump(),
            gold_set_version=gold_set_version,
            judge_config_version=judge_config_version,
            judge_config=bundle,
            max_cost_usd=max_cost_usd,
            n_examples_total=0,
            status="running",
            error={"step": failure.step, "cause": str(failure.cause)},
            experiment_id=experiment_id,
            test=test,
        )
        return _finish_run(
            run_id=run_id,
            status="halted_setup",
            started_at=started_at,
            cost_actual_usd=0.0,
            n_examples_scored=0,
            n_examples_errored=0,
            halt_error={"step": failure.step, "cause": str(failure.cause)},
            teardown_hook=teardown_hook,
            test=test,
        )
```

- [ ] **Step 4: Add the common teardown/finalize helpers**

Add before the existing database helper functions:

```python
def _apply_teardown_outcome(
    status: str,
    error: dict | None,
    receipt: dict[str, object],
) -> tuple[str, dict | None]:
    if receipt.get("success") is not False:
        return status, error
    return (
        "halted_teardown_failed",
        {
            "cause": "compute teardown failed",
            "pre_teardown_status": status,
            "pre_teardown_error": error,
            "teardown_receipt": receipt,
        },
    )


def _finish_run(
    *,
    run_id: uuid.UUID,
    status: str,
    started_at: float,
    cost_actual_usd: float,
    n_examples_scored: int,
    n_examples_errored: int,
    halt_error: dict | None,
    teardown_hook: TeardownHook,
    test: bool,
) -> RunResult:
    receipt = teardown_hook.teardown(f"run_finalize_{status}")
    final_status, final_error = _apply_teardown_outcome(status, halt_error, receipt)
    finished_at = time.time()
    _finalize_run_row(
        run_id=run_id,
        status=final_status,
        finished_at=finished_at,
        wall_seconds=int(finished_at - started_at),
        cost_actual_usd=cost_actual_usd,
        n_examples_scored=n_examples_scored,
        n_examples_errored=n_examples_errored,
        summary_scores=_compute_summary(run_id, test=test),
        error=final_error,
        notes=f"teardown_receipt={json.dumps(receipt)}",
        test=test,
    )
    return RunResult(
        run_id=run_id,
        status=final_status,
        cost_actual_usd=cost_actual_usd,
        n_examples_scored=n_examples_scored,
        n_examples_errored=n_examples_errored,
    )
```

- [ ] **Step 5: Route normal and setup exits through `_finish_run`**

Replace the normal teardown/finalize block at the end of `run_campaign` with:

```python
    return _finish_run(
        run_id=run_id,
        status=status,
        started_at=started_at,
        cost_actual_usd=cost_accumulated,
        n_examples_scored=n_scored,
        n_examples_errored=n_errored,
        halt_error=halt_error,
        teardown_hook=teardown_hook,
        test=test,
    )
```

For each DB-writable preflight/privacy setup failure, write the initial row with `status="running"`, then replace the direct teardown and `RunResult(...)` return with `_finish_run(...)` using status `halted_setup` and zero cost/counts.

For the PostgreSQL preflight failure branch, replace the bare raise with:

```python
        if f.step == "postgres":
            teardown_hook.teardown("run_finalize_postgres_failure")
            raise
```

Do not call teardown anywhere else; each path must call it exactly once.

- [ ] **Step 6: Run lifecycle tests to verify GREEN**

```bash
uv run pytest tests/integration/test_runner.py -v
```

Expected: all runner integration tests pass, including the six new lifecycle cases.

- [ ] **Step 7: Run the full suite and Ruff**

```bash
uv run pytest -q
uv run ruff check .
```

Expected: all tests pass and Ruff is clean.

- [ ] **Step 8: Commit runner integration**

```bash
git add shared/eval/runner/runner.py tests/integration/test_runner.py
git commit -m "feat: enforce teardown ownership for cloud campaigns"
```

---

### Task 3: Add the explicit CLI workspace option

**Files:**
- Create: `tests/shared/eval/test_runner_cli.py`
- Modify: `shared/eval/runner/cli.py`

**Interfaces:**
- Consumes: `run_campaign(..., terraform_workspace: Path | None)`.
- Produces: `build_parser() -> argparse.ArgumentParser` and `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write failing CLI tests**

Create `tests/shared/eval/test_runner_cli.py`:

```python
"""Tests for eval-runner CLI argument wiring."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from shared.eval.runner.cli import build_parser, main
from shared.eval.runner.runner import RunResult


def test_parser_accepts_terraform_workspace() -> None:
    args = build_parser().parse_args([
        "--model", "m",
        "--gold-set", "g",
        "--judge-config", "j",
        "--max-cost-usd", "1.0",
        "--template-root", "templates",
        "--terraform-workspace", "infra/gcp",
    ])
    assert args.terraform_workspace == Path("infra/gcp")


def test_main_passes_workspace_to_runner() -> None:
    result = RunResult(UUID(int=0), "completed", 0.0, 1, 0)
    argv = [
        "--model", "m",
        "--gold-set", "g",
        "--judge-config", "j",
        "--max-cost-usd", "1.0",
        "--template-root", "templates",
        "--terraform-workspace", "infra/gcp",
    ]
    with patch("shared.eval.runner.cli.run_campaign", return_value=result) as run:
        assert main(argv) == 0
    assert run.call_args.kwargs["terraform_workspace"] == Path("infra/gcp")
```

- [ ] **Step 2: Run CLI tests to verify RED**

```bash
uv run pytest tests/shared/eval/test_runner_cli.py -v
```

Expected: import failure because `build_parser` and `main` do not exist.

- [ ] **Step 3: Refactor the CLI without changing existing arguments**

Replace the executable portion of `shared/eval/runner/cli.py` with:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--gold-set", required=True, dest="gold_set_version")
    parser.add_argument("--judge-config", required=True, dest="judge_config_version")
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--template-root", required=True, type=Path)
    parser.add_argument("--experiment", default=None, dest="experiment_id")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--terraform-workspace", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rr = run_campaign(
        model_id=args.model,
        gold_set_version=args.gold_set_version,
        judge_config_version=args.judge_config_version,
        max_cost_usd=args.max_cost_usd,
        template_root=args.template_root,
        experiment_id=args.experiment_id,
        test=args.test,
        terraform_workspace=args.terraform_workspace,
    )
    print(
        f"run_id={rr.run_id} status={rr.status} "
        f"cost=${rr.cost_actual_usd:.6f} "
        f"scored={rr.n_examples_scored} errored={rr.n_examples_errored}"
    )
    return 0 if rr.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
```

Delete the old `_cli()` function and old `if __name__` block. Keep `sys` because the new block uses it.

- [ ] **Step 4: Run CLI tests to verify GREEN**

```bash
uv run pytest tests/shared/eval/test_runner_cli.py -v
uv run ruff check shared/eval/runner/cli.py tests/shared/eval/test_runner_cli.py
```

Expected: both tests pass and Ruff is clean.

- [ ] **Step 5: Commit the CLI option**

```bash
git add shared/eval/runner/cli.py tests/shared/eval/test_runner_cli.py
git commit -m "feat: expose Terraform workspace on eval CLI"
```

---

### Task 4: Convert all GCP workspaces to private tunnels and ephemeral state

**Files:**
- Modify: `infra/gcp/main.tf`
- Modify: `infra/gcp/outputs.tf`
- Modify: `infra/gcp/startup.sh.tpl`
- Modify: `infra/gcp/Makefile`
- Modify: `infra/gcp/judge/main.tf`
- Modify: `infra/gcp/judge/outputs.tf`
- Modify: `infra/gcp/judge/startup.sh.tpl`
- Modify: `infra/gcp/judge/Makefile`
- Modify: `infra/gcp/annotation/main.tf`
- Modify: `infra/gcp/annotation/outputs.tf`
- Modify: `infra/gcp/annotation/Makefile`
- Modify: `shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml`
- Modify: `shared/models/registry/qwen2.5-72b-instruct-awq-vllm-a2.yaml`
- Modify: `shared/eval/judges/configs/v0.2.yaml`

**Interfaces:**
- Produces local endpoints `http://127.0.0.1:8000/v1`, `http://127.0.0.1:8001/v1`, and `http://127.0.0.1:6900`.
- Produces Make targets `tunnel` for eval/annotation and `judge-tunnel` for judge.
- Removes all GCS bucket, static-address, and custom-firewall resources.

- [ ] **Step 1: Install Terraform and capture its version**

Run:

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
terraform version
```

Expected: Terraform reports an installed version and no command is missing.

- [ ] **Step 2: Remove public and persistent resources from the eval workspace**

In `infra/gcp/main.tf`, delete `google_storage_bucket.model_cache`, `google_compute_address.vllm_ip`, and `google_compute_firewall.vllm_inference`. Change the network interface to:

```hcl
  network_interface {
    network = "default"
    access_config {}
  }
```

Change the startup template arguments to:

```hcl
  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      model_id       = var.model_id
      model_revision = var.model_revision
      hf_token       = var.hf_token
      vllm_version   = var.vllm_version
    })
  }
```

Change service-account scopes to logging and monitoring only:

```hcl
  service_account {
    scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
    ]
  }
```

- [ ] **Step 3: Make eval startup download directly to the boot disk**

In `infra/gcp/startup.sh.tpl`, delete `BUCKET`, `SENTINEL`, every `gsutil` command, and the cache branch. Keep token setup and replace the download section with:

```bash
echo "[startup] model_id=$MODEL_ID revision=$MODEL_REVISION vllm=$VLLM_VERSION"

if [ -n "$HF_TOKEN" ]; then
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

mkdir -p "$LOCAL_MODEL_DIR"
pip install -q "huggingface_hub[cli]"
huggingface-cli download "$MODEL_ID" \
  --revision "$MODEL_REVISION" \
  --local-dir "$LOCAL_MODEL_DIR" \
  --local-dir-use-symlinks False
```

Keep the existing Docker and health-gate blocks unchanged.

- [ ] **Step 4: Replace eval outputs and Make targets**

Replace `infra/gcp/outputs.tf` with:

```hcl
output "endpoint_url" {
  value       = "http://127.0.0.1:8000/v1"
  description = "Inference endpoint through `make tunnel`."
}

output "instance_name" {
  value       = google_compute_instance.vllm.name
  description = "GCE instance name used by SSH and the tunnel."
}
```

Replace `infra/gcp/Makefile` with:

```makefile
ZONE ?= asia-southeast1-b

.PHONY: up down tunnel health ssh

up:
	terraform apply -auto-approve -input=false

down:
	terraform destroy -auto-approve -input=false

tunnel:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE) -- -N -L 8000:127.0.0.1:8000

health:
	@until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 5; done
	@echo "Ready: http://127.0.0.1:8000/v1"

ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
```

- [ ] **Step 5: Apply the same isolation to the judge workspace**

In `infra/gcp/judge/main.tf`, delete the bucket data source, static address, and firewall resource. Use `access_config {}` with no `nat_ip`. Remove `bucket_name` from template arguments and remove the storage scope.

In `infra/gcp/judge/startup.sh.tpl`, replace the bucket/cache section with the direct-download block from Step 3. Keep the judge-specific vLLM flags.

Replace `infra/gcp/judge/outputs.tf` with:

```hcl
output "judge_endpoint_url" {
  value       = "http://127.0.0.1:8001/v1"
  description = "Judge endpoint through `make judge-tunnel`."
}

output "instance_name" {
  value       = google_compute_instance.judge.name
  description = "GCE instance name used by SSH and the tunnel."
}
```

Replace the judge Makefile targets with:

```makefile
ZONE ?= asia-southeast1-b

.PHONY: judge-up judge-down judge-tunnel judge-health judge-ssh

judge-up:
	terraform apply -auto-approve -input=false

judge-down:
	terraform destroy -auto-approve -input=false

judge-tunnel:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE) -- -N -L 8001:127.0.0.1:8000

judge-health:
	@until curl -sf http://127.0.0.1:8001/health >/dev/null; do sleep 5; done
	@echo "Ready: http://127.0.0.1:8001/v1"

judge-ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
```

- [ ] **Step 6: Isolate the annotation workspace**

In `infra/gcp/annotation/main.tf`, delete the static address and firewall resources. Use `access_config {}` with no `nat_ip`, remove instance tags, and remove the storage scope.

Replace `infra/gcp/annotation/outputs.tf` with:

```hcl
output "argilla_url" {
  value       = "http://127.0.0.1:6900"
  description = "Argilla URL through `make tunnel`."
}

output "instance_name" {
  value       = google_compute_instance.argilla.name
  description = "GCE instance name used by SSH and the tunnel."
}
```

Replace `infra/gcp/annotation/Makefile` with:

```makefile
ZONE ?= asia-southeast1-b

.PHONY: up down tunnel health ssh

up:
	terraform apply -auto-approve -input=false

down:
	terraform destroy -auto-approve -input=false

tunnel:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE) -- -N -L 6900:127.0.0.1:6900

health:
	@until curl -sf http://127.0.0.1:6900/api/v1/status >/dev/null; do sleep 5; done
	@echo "Ready: http://127.0.0.1:6900"

ssh:
	gcloud compute ssh "$$(terraform output -raw instance_name)" --zone $(ZONE)
```

- [ ] **Step 7: Replace endpoint placeholders with tunnel endpoints**

Set the L4 manifest endpoint to:

```yaml
endpoint: "http://127.0.0.1:8000/v1"
```

Set the A100 judge manifest and `shared/eval/judges/configs/v0.2.yaml` judge endpoint to:

```yaml
endpoint: "http://127.0.0.1:8001/v1"
```

- [ ] **Step 8: Format and validate all workspaces**

Run:

```bash
terraform fmt -recursive infra/gcp
terraform -chdir=infra/gcp init -backend=false
terraform -chdir=infra/gcp validate
terraform -chdir=infra/gcp/judge init -backend=false
terraform -chdir=infra/gcp/judge validate
terraform -chdir=infra/gcp/annotation init -backend=false
terraform -chdir=infra/gcp/annotation validate
rg -n '0\.0\.0\.0/0|google_compute_firewall|google_compute_address|google_storage_bucket|PLACEHOLDER' infra/gcp shared/models/registry shared/eval/judges/configs/v0.2.yaml
```

Expected: every validate command reports success; the final search returns no matches.

- [ ] **Step 9: Run Python verification**

```bash
uv run pytest -q
uv run ruff check .
```

Expected: all tests pass and Ruff is clean.

- [ ] **Step 10: Commit private, ephemeral cloud configuration**

```bash
git add infra/gcp shared/models/registry/qwen2.5-7b-instruct-vllm-l4.yaml \
  shared/models/registry/qwen2.5-72b-instruct-awq-vllm-a2.yaml \
  shared/eval/judges/configs/v0.2.yaml
git commit -m "fix: isolate cloud services behind disposable SSH tunnels"
```

---

### Task 5: Add reproducible cloud lifecycle smoke fixtures

**Files:**
- Create: `experiments/0002-eval-cloud-lifecycle/README.md`
- Create: `experiments/0002-eval-cloud-lifecycle/prompt_templates/general/qa.j2`
- Create: `experiments/0002-eval-cloud-lifecycle/exact.jsonl`
- Create: `experiments/0002-eval-cloud-lifecycle/rubric.jsonl`
- Modify: `EXPERIMENTS.md`

**Interfaces:**
- Produces immutable smoke versions `cloud-smoke-v0.0` and `judge-smoke-v0.0`.
- Produces experiment ID `0002-eval-cloud-lifecycle` for both live operational gates.

- [ ] **Step 1: Create the prompt template**

Create `prompt_templates/general/qa.j2`:

```jinja2
{{ question }}
```

- [ ] **Step 2: Create the deterministic L4 smoke example**

Create `exact.jsonl` as one JSON line:

```json
{"example_id":"ex_general_cloud0001","lane":"general","source":"handcrafted operational smoke","annotator":"huiliang","annotated_at":"2026-07-18","prompt_template":"general/qa.j2","inputs":{"question":"Compute 2 + 2. Reply with only the number."},"expected":{"type":"exact","value":"4"},"provenance_tag":"public","never_to_third_party":false,"tags":["smoke"],"contamination_risk":"none"}
```

- [ ] **Step 3: Create the rubric judge smoke example**

Create `rubric.jsonl` as one JSON line:

```json
{"example_id":"ex_general_judge0001","lane":"general","source":"handcrafted operational smoke","annotator":"huiliang","annotated_at":"2026-07-18","prompt_template":"general/qa.j2","inputs":{"question":"In two sentences, explain why plants need light for photosynthesis."},"expected":{"type":"rubric","rubric":"Award 1.0 if the response states that light supplies energy used to convert carbon dioxide and water into chemical energy or sugars, and does not claim that light is matter consumed by the plant. Award 0.5 if it correctly says light provides energy but omits the conversion. Award 0.0 for an incorrect explanation.","reference":"Light supplies the energy for photosynthesis, allowing plants to convert carbon dioxide and water into sugars while releasing oxygen."},"provenance_tag":"public","never_to_third_party":false,"tags":["smoke"],"contamination_risk":"none"}
```

- [ ] **Step 4: Validate both fixtures through the production schema**

Run:

```bash
uv run python -c "from pathlib import Path; from shared.goldsets.loader import load_jsonl_to_postgres; print(load_jsonl_to_postgres(Path('experiments/0002-eval-cloud-lifecycle/exact.jsonl'), 'cloud-smoke-v0.0', 'fixture-cloud-v0', test=True))"
uv run python -c "from pathlib import Path; from shared.goldsets.loader import load_jsonl_to_postgres; print(load_jsonl_to_postgres(Path('experiments/0002-eval-cloud-lifecycle/rubric.jsonl'), 'judge-smoke-v0.0', 'fixture-judge-v0', test=True))"
```

Expected: each command loads one example into the test database. Resetting the test database later is allowed; this step proves schema validity.

- [ ] **Step 5: Write the experiment README**

Document hypothesis, setup, method, explicit cleanup requirement, deterministic acceptance criteria, rubric acceptance criteria, cost fields, teardown receipt fields, and a Results section that begins with `Status: not yet run`. Do not include claimed run IDs or costs before the live tasks execute.

- [ ] **Step 6: Register the running experiment**

Add to `EXPERIMENTS.md`:

```markdown
| 0002 | eval | cloud-lifecycle | running | 2026-07-18 | private-tunnel L4 and A100 judge smoke; awaiting live evidence and zero-resource final inventory |
```

- [ ] **Step 7: Commit the smoke fixtures**

```bash
git add experiments/0002-eval-cloud-lifecycle EXPERIMENTS.md
git commit -m "test: add live cloud lifecycle smoke fixtures"
```

---

### Task 6: Execute and destroy the live L4 campaign

**Files:**
- Runtime-only: `infra/gcp/terraform.tfvars` (gitignored)
- Modify after evidence: `experiments/0002-eval-cloud-lifecycle/README.md`

**Interfaces:**
- Consumes: L4 workspace, tunnel endpoint, cloud smoke fixture, and runner Terraform hook.
- Produces: one completed `cloud-smoke-v0.0` run whose notes contain a successful Terraform destroy receipt.

- [ ] **Step 1: Capture the empty pre-run inventory**

Run:

```bash
gcloud compute instances list --project adept-prod-497323
gcloud compute disks list --project adept-prod-497323
gcloud compute addresses list --project adept-prod-497323
gcloud storage buckets list --project adept-prod-497323
```

Expected: no resources created by this recovery. Stop and reconcile ownership if any unexpected resource appears.

- [ ] **Step 2: Create exact eval workspace variables**

Create gitignored `infra/gcp/terraform.tfvars`:

```hcl
project_id     = "adept-prod-497323"
zone           = "asia-southeast1-b"
instance_type  = "g2-standard-8"
model_id       = "Qwen/Qwen2.5-7B-Instruct"
model_revision = "main"
vllm_version   = "v0.4.3"
hf_token       = ""
preemptible    = true
```

- [ ] **Step 3: Sync runtime metadata and smoke data**

```bash
uv run python -m shared.db.migrations apply
uv run python -c "from shared.models.registry import sync_all; print(sync_all())"
uv run python -c "from shared.eval.judges import register_bundle; register_bundle('v0.1'); print('registered v0.1')"
uv run python -c "from pathlib import Path; from shared.goldsets.loader import load_jsonl_to_postgres; print(load_jsonl_to_postgres(Path('experiments/0002-eval-cloud-lifecycle/exact.jsonl'), 'cloud-smoke-v0.0', 'fixture-cloud-v0'))"
```

Expected: metadata commands succeed and the loader prints 1 on first load or 0 on idempotent repeat.

- [ ] **Step 4: Apply the L4 workspace**

```bash
terraform -chdir=infra/gcp apply -auto-approve -input=false
```

Expected: one `vllm-eval-server` instance is created. On any apply failure, immediately run `terraform -chdir=infra/gcp destroy -auto-approve -input=false`, verify inventory, and stop this task.

- [ ] **Step 5: Start the eval SSH tunnel in a dedicated terminal/session**

```bash
make -C infra/gcp tunnel
```

Keep the session open. In the main terminal, run:

```bash
make -C infra/gcp health
```

Expected: health reports `Ready: http://127.0.0.1:8000/v1`.

- [ ] **Step 6: Run the deterministic cloud campaign with automatic destroy**

```bash
uv run python -m shared.eval.runner.cli \
  --model Qwen/Qwen2.5-7B-Instruct \
  --gold-set cloud-smoke-v0.0 \
  --judge-config v0.1 \
  --max-cost-usd 1.00 \
  --template-root experiments/0002-eval-cloud-lifecycle/prompt_templates \
  --experiment 0002-eval-cloud-lifecycle \
  --terraform-workspace infra/gcp
```

Expected: `status=completed`, one scored result, zero errors. The tunnel exits when Terraform destroys the instance.

- [ ] **Step 7: Verify run and teardown evidence**

```bash
/Library/PostgreSQL/17/bin/psql -h /tmp -d ai_experiments -U huiliang -P pager=off -c "SELECT status, model_id, cost_actual_usd, n_examples_scored, n_examples_errored, notes FROM run WHERE experiment_id='0002-eval-cloud-lifecycle' AND gold_set_version='cloud-smoke-v0.0' ORDER BY started_at DESC LIMIT 1;"
gcloud compute instances list --project adept-prod-497323
gcloud compute disks list --project adept-prod-497323
gcloud compute addresses list --project adept-prod-497323
gcloud storage buckets list --project adept-prod-497323
```

Expected: completed run; notes contain `"success": true`; all four inventories are empty.

- [ ] **Step 8: Record exact L4 evidence in the README**

Replace the L4 `Status: not yet run` subsection with the actual run ID, model, cost, score, teardown receipt return code, and post-destroy inventory result emitted above.

- [ ] **Step 9: Commit L4 evidence**

```bash
git add experiments/0002-eval-cloud-lifecycle/README.md
git commit -m "docs: record disposable L4 smoke evidence"
```

---

### Task 7: Execute and destroy the live A100 judge campaign

**Files:**
- Runtime-only: `infra/gcp/judge/terraform.tfvars` (gitignored)
- Modify: `experiments/0002-eval-cloud-lifecycle/README.md`
- Modify: `EXPERIMENTS.md`

**Interfaces:**
- Consumes: local Mac inference at port 11434, A100 judge tunnel at port 8001, v0.2 bundle, and rubric fixture.
- Produces: one completed `judge-smoke-v0.0` run with an LLM judgement and successful judge-workspace destroy receipt.

- [ ] **Step 1: Create exact judge workspace variables**

Create gitignored `infra/gcp/judge/terraform.tfvars`:

```hcl
project_id           = "adept-prod-497323"
zone                 = "asia-southeast1-b"
judge_model_id       = "Qwen/Qwen2.5-72B-Instruct-AWQ"
judge_model_revision = "main"
vllm_version         = "v0.4.3"
hf_token             = ""
preemptible          = true
```

- [ ] **Step 2: Sync v0.2 and load rubric smoke data**

```bash
uv run python -c "from shared.models.registry import sync_all; print(sync_all())"
uv run python -c "from shared.eval.judges import register_bundle; register_bundle('v0.2'); print('registered v0.2')"
uv run python -c "from pathlib import Path; from shared.goldsets.loader import load_jsonl_to_postgres; print(load_jsonl_to_postgres(Path('experiments/0002-eval-cloud-lifecycle/rubric.jsonl'), 'judge-smoke-v0.0', 'fixture-judge-v0'))"
curl -fsS http://127.0.0.1:11434/api/tags
```

Expected: metadata and loader succeed; Ollama is healthy with the Mac model available.

- [ ] **Step 3: Apply the judge workspace**

```bash
terraform -chdir=infra/gcp/judge apply -auto-approve -input=false
```

Expected: one `vllm-judge-server` A100 instance is created. On quota, capacity, apply, or startup failure, immediately destroy the workspace, verify empty inventory, record the blocker, and do not change machine class or preemptibility.

- [ ] **Step 4: Start and verify the judge tunnel**

In a dedicated terminal/session:

```bash
make -C infra/gcp/judge judge-tunnel
```

In the main terminal:

```bash
make -C infra/gcp/judge judge-health
```

Expected: `Ready: http://127.0.0.1:8001/v1`.

- [ ] **Step 5: Run the rubric campaign with judge-workspace ownership**

```bash
uv run python -m shared.eval.runner.cli \
  --model qwen2.5:0.5b-instruct \
  --gold-set judge-smoke-v0.0 \
  --judge-config v0.2 \
  --max-cost-usd 1.00 \
  --template-root experiments/0002-eval-cloud-lifecycle/prompt_templates \
  --experiment 0002-eval-cloud-lifecycle \
  --terraform-workspace infra/gcp/judge
```

Expected: `status=completed`, one scored result, zero errors; the judgement row contains `judge_role=lm_judge`, parsed score, raw response, rationale, usage, cost, and wall time. The judge instance is destroyed during finalization.

- [ ] **Step 6: Verify judge persistence and zero residual resources**

```bash
/Library/PostgreSQL/17/bin/psql -h /tmp -d ai_experiments -U huiliang -P pager=off -c "SELECT r.status, r.cost_actual_usd, r.notes, j.judge_role, j.score, j.parse_error, j.raw_response IS NOT NULL AS raw_preserved, j.cost_increment_usd FROM run r JOIN result x ON x.run_id=r.id JOIN judgement j ON j.result_id=x.id WHERE r.experiment_id='0002-eval-cloud-lifecycle' AND r.gold_set_version='judge-smoke-v0.0' ORDER BY r.started_at DESC LIMIT 1;"
gcloud compute instances list --project adept-prod-497323
gcloud compute disks list --project adept-prod-497323
gcloud compute addresses list --project adept-prod-497323
gcloud storage buckets list --project adept-prod-497323
```

Expected: completed, parsed LM judgement, raw response preserved, successful teardown receipt, and empty inventories.

- [ ] **Step 7: Record evidence or the exact blocker**

If successful, replace the judge `Status: not yet run` subsection with emitted evidence and change experiment 0002 to `done` with result `private-tunnel L4 and A100 judge campaigns completed; Terraform receipts successful; final GCP inventory empty`.

If blocked by quota/capacity/startup, record the exact command, error class, cleanup command, and empty final inventory; leave experiment status `running` and do not claim the judge gate passed.

- [ ] **Step 8: Run final verification**

```bash
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/gcp
git diff --check
```

Expected: all local gates pass. Live-gate success is determined only by Task 6/7 evidence and empty inventory.

- [ ] **Step 9: Commit final cloud evidence**

```bash
git add experiments/0002-eval-cloud-lifecycle/README.md EXPERIMENTS.md
git commit -m "docs: record sovereign cloud lifecycle result"
```

---

### Task 8: Draft the Phase 1 documentation milestone from verified evidence

**Files:**
- Create: `docs/writeups/phase-1-sovereign-inference-substrate.md`
- Create: `docs/social/phase-1-sovereign-inference-substrate.md`
- Modify after publication approval: `docs/writeups/phase-1-sovereign-inference-substrate.md`
- Modify after publication approval: `ROADMAP.md`

**Interfaces:**
- Consumes: preserved Mac, L4, A100 judge, cost, and teardown evidence from experiments 0001 and 0002.
- Produces: the long-form source draft and short-form bundle required by the Phase 1 documentation gate.

- [ ] **Step 1: Create the long-form source with an evidence-only structure**

Create `docs/writeups/phase-1-sovereign-inference-substrate.md` with this front matter:

```yaml
---
title: "Building a sovereign LLM inference substrate: Mac and disposable GCP behind one contract"
status: draft
canonical_url: null
hubspot_excerpt_url: null
date_started: 2026-07-18
---
```

Use these exact top-level sections:

```markdown
# Building a sovereign LLM inference substrate: Mac and disposable GCP behind one contract

## What sovereignty means in this lab
## The contract shared by Mac and GCP
## What experiment 0001 proved on the Mac
## Why software scaffolding was not operational evidence
## Private SSH tunnels and disposable infrastructure
## The L4 campaign: latency, score, and measured cost
## The A100 judge campaign: rubric trace and measured cost
## Automatic teardown as part of correctness
## What remains open: DGX Spark and calibrated judging
## Reproduction guide
## Limitations
```

Populate every result claim from the committed experiment READMEs and preserved Postgres rows.
Do not describe Spark as tested, v0.2 as calibrated, or a blocked A100 run as successful. If the
A100 task is blocked, the corresponding section reports the blocker and verified cleanup.

- [ ] **Step 2: Create the short-form bundle**

Create `docs/social/phase-1-sovereign-inference-substrate.md` with these sections:

```markdown
# Phase 1 social bundle — sovereign inference substrate

## LinkedIn primary post
## Substack Note
## X / Bluesky / Mastodon thread
## HubSpot excerpt
## Claims and source checks
```

The LinkedIn and thread versions must include only numbers present in the two experiment READMEs.
The claims/source-check section maps each numeric claim to the experiment, run ID, and Postgres
field that supports it. The HubSpot excerpt is three paragraphs and ends by directing readers to
the canonical Substack article without inventing a URL before publication.

- [ ] **Step 3: Check drafts for unsupported completion language**

Run:

```bash
rg -n 'Spark.*(complete|validated|passed)|calibrated|production-ready|PLACEHOLDER|TBD|TODO' \
  docs/writeups/phase-1-sovereign-inference-substrate.md \
  docs/social/phase-1-sovereign-inference-substrate.md
git diff --check
```

Expected: no unsupported completion, placeholder, or formatting findings. Legitimate sentences
that explicitly say the judge is not calibrated are allowed after manual inspection.

- [ ] **Step 4: Commit the evidence-backed drafts**

```bash
git add docs/writeups/phase-1-sovereign-inference-substrate.md \
  docs/social/phase-1-sovereign-inference-substrate.md
git commit -m "docs: draft Phase 1 sovereign substrate publication"
```

- [ ] **Step 5: Pause for publication authorization and human editorial review**

Publishing to Substack, HubSpot, or social networks changes external state. Present the committed
drafts and exact target accounts to the user. Do not publish without explicit authorization for
those accounts.

- [ ] **Step 6: Record publication evidence only after authorized publication**

After the user publishes or explicitly authorizes publishing, set `status: published`, record the
actual Substack canonical URL and HubSpot excerpt URL in front matter, record social-post URLs in
the social bundle, and update Phase 1's ROADMAP status only if every technical acceptance criterion
also passed. If Spark remains unavailable, keep Phase 1 `in progress` and describe the published
Mac/GCP milestone without claiming the entire phase is complete.

- [ ] **Step 7: Commit publication URLs and truthful phase status**

```bash
git add docs/writeups/phase-1-sovereign-inference-substrate.md \
  docs/social/phase-1-sovereign-inference-substrate.md ROADMAP.md
git commit -m "docs: record Phase 1 publication evidence"
```
