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
