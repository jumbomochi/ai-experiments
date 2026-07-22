"""Canonical GCP project configuration and active-target verification."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


class ProjectConfigError(ValueError):
    """Raised when a project configuration file violates the contract."""


class TargetMismatchError(ProjectConfigError):
    """Raised when the configured or active gcloud target is unsafe."""


_KEY_TO_FIELD = {
    "GCLOUD_CONFIGURATION": "gcloud_configuration",
    "GCLOUD_ACCOUNT": "gcloud_account",
    "GCP_PROJECT_ID": "project_id",
    "GCP_REGION": "region",
    "GCP_ZONE": "zone",
    "GCP_TERRAFORM_SERVICE_ACCOUNT": "terraform_service_account",
    "GCP_STATE_BUCKET": "state_bucket",
}
_REQUIRED_ACCOUNT = "huiliang@sgcodecampus.com"
_REQUIRED_CONFIGURATION = "ai-experiments"
_ALLOWED_PROJECTS = frozenset({"sgcc-ai-experiments", "sgcc-ai-experiments-66bdf1"})


@dataclass(frozen=True)
class ProjectConfig:
    gcloud_configuration: str
    gcloud_account: str
    project_id: str
    region: str
    zone: str
    terraform_service_account: str
    state_bucket: str

    @classmethod
    def from_file(cls, path: Path) -> ProjectConfig:
        """Load a strict, non-shell project configuration file."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ProjectConfigError(f"cannot read project configuration {path}: {exc}") from exc

        values: dict[str, str] = {}
        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export"):
                raise ProjectConfigError(f"line {line_number}: export syntax is not allowed")
            if "=" not in line:
                raise ProjectConfigError(f"line {line_number}: expected KEY=value")

            key, value = line.split("=", maxsplit=1)
            if key not in _KEY_TO_FIELD:
                raise ProjectConfigError(f"line {line_number}: unexpected key {key!r}")
            if key in values:
                raise ProjectConfigError(f"line {line_number}: duplicate key {key}")
            if not value:
                raise ProjectConfigError(f"line {line_number}: {key} must not be empty")
            if "$" in value or "`" in value:
                raise ProjectConfigError(f"line {line_number}: shell syntax is not allowed")
            if '"' in value or "'" in value:
                raise ProjectConfigError(f"line {line_number}: quotes are not allowed")
            values[key] = value

        missing = [key for key in _KEY_TO_FIELD if key not in values]
        if missing:
            raise ProjectConfigError(f"missing required keys: {', '.join(missing)}")
        if values["GCLOUD_ACCOUNT"] != _REQUIRED_ACCOUNT:
            raise ProjectConfigError(f"GCLOUD_ACCOUNT must be {_REQUIRED_ACCOUNT}")

        return cls(**{field: values[key] for key, field in _KEY_TO_FIELD.items()})

    def verify_gcloud(
        self,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        """Fail unless gcloud's active account and project exactly match this contract."""
        self._reject_unsafe_target()

        account = self._get_gcloud_value("account", runner)
        if account != self.gcloud_account:
            raise TargetMismatchError(
                f"gcloud account mismatch: expected {self.gcloud_account}, got {account}"
            )

        project = self._get_gcloud_value("project", runner)
        if project != self.project_id:
            raise TargetMismatchError(
                f"gcloud project mismatch: expected {self.project_id}, got {project}"
            )

    def _reject_unsafe_target(self) -> None:
        if self.gcloud_account != _REQUIRED_ACCOUNT:
            raise TargetMismatchError(f"GCLOUD_ACCOUNT must be {_REQUIRED_ACCOUNT}")
        if self.gcloud_configuration != _REQUIRED_CONFIGURATION:
            raise TargetMismatchError(
                f"gcloud configuration must be {_REQUIRED_CONFIGURATION}"
            )
        if self.project_id not in _ALLOWED_PROJECTS:
            allowed_projects = ", ".join(sorted(_ALLOWED_PROJECTS))
            raise TargetMismatchError(f"GCP project must be one of: {allowed_projects}")

    def _get_gcloud_value(
        self,
        property_name: str,
        runner: Callable[..., subprocess.CompletedProcess[str]],
    ) -> str:
        command = [
            "gcloud",
            "config",
            "get-value",
            property_name,
            f"--configuration={self.gcloud_configuration}",
        ]
        try:
            result = runner(
                command,
                check=True,
                capture_output=True,
                text=True,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise TargetMismatchError(f"could not verify gcloud {property_name}: {exc}") from exc
        return result.stdout.strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--check-gcloud", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = ProjectConfig.from_file(args.file)
        if args.check_gcloud:
            config.verify_gcloud(runner=subprocess.run)
            print(f"target verified: {config.project_id}")
    except ProjectConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
