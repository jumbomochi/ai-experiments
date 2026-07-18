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
