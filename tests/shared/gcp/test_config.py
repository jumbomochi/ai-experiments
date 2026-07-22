from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

import shared.gcp.config as config_module
from shared.gcp.config import ProjectConfig, ProjectConfigError, TargetMismatchError


VALID_VALUES = {
    "GCLOUD_CONFIGURATION": "ai-experiments",
    "GCLOUD_ACCOUNT": "huiliang@sgcodecampus.com",
    "GCP_PROJECT_ID": "sgcc-ai-experiments",
    "GCP_REGION": "asia-southeast1",
    "GCP_ZONE": "asia-southeast1-b",
    "GCP_TERRAFORM_SERVICE_ACCOUNT": (
        "terraform-ai-experiments@sgcc-ai-experiments.iam.gserviceaccount.com"
    ),
    "GCP_STATE_BUCKET": "sgcc-ai-experiments-tfstate",
}


def _write_config(
    tmp_path: Path,
    *,
    values: dict[str, str] | None = None,
    extra_lines: list[str] | None = None,
) -> Path:
    config_values = VALID_VALUES if values is None else values
    lines = ["# Dedicated project target", ""]
    lines.extend(f"{key}={value}" for key, value in config_values.items())
    lines.extend(extra_lines or [])
    path = tmp_path / "project.env"
    path.write_text("\n".join(lines) + "\n")
    return path


def _project_config(**overrides: str) -> ProjectConfig:
    values = {
        "gcloud_configuration": "ai-experiments",
        "gcloud_account": "huiliang@sgcodecampus.com",
        "project_id": "sgcc-ai-experiments",
        "region": "asia-southeast1",
        "zone": "asia-southeast1-b",
        "terraform_service_account": (
            "terraform-ai-experiments@sgcc-ai-experiments.iam.gserviceaccount.com"
        ),
        "state_bucket": "sgcc-ai-experiments-tfstate",
    }
    values.update(overrides)
    return ProjectConfig(**values)


@pytest.mark.parametrize("missing_key", VALID_VALUES)
def test_from_file_rejects_each_missing_required_key(tmp_path: Path, missing_key: str) -> None:
    values = {key: value for key, value in VALID_VALUES.items() if key != missing_key}

    with pytest.raises(ProjectConfigError, match=missing_key):
        ProjectConfig.from_file(_write_config(tmp_path, values=values))


def test_from_file_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        extra_lines=["GCP_REGION=us-central1"],
    )

    with pytest.raises(ProjectConfigError, match="duplicate.*GCP_REGION"):
        ProjectConfig.from_file(path)


@pytest.mark.parametrize(
    "unsafe_value",
    ["${HOME}", "$(whoami)", "`whoami`"],
)
def test_from_file_rejects_shell_expansion_syntax(
    tmp_path: Path,
    unsafe_value: str,
) -> None:
    values = {**VALID_VALUES, "GCP_REGION": unsafe_value}

    with pytest.raises(ProjectConfigError, match="shell syntax"):
        ProjectConfig.from_file(_write_config(tmp_path, values=values))


@pytest.mark.parametrize("quoted_value", ['"asia-southeast1"', "'asia-southeast1'"])
def test_from_file_rejects_quoted_values(tmp_path: Path, quoted_value: str) -> None:
    values = {**VALID_VALUES, "GCP_REGION": quoted_value}

    with pytest.raises(ProjectConfigError, match="quotes"):
        ProjectConfig.from_file(_write_config(tmp_path, values=values))


def test_from_file_rejects_export_syntax(tmp_path: Path) -> None:
    values = dict(VALID_VALUES)
    account = values.pop("GCLOUD_ACCOUNT")

    with pytest.raises(ProjectConfigError, match="export"):
        ProjectConfig.from_file(
            _write_config(tmp_path, values=values, extra_lines=[f"export GCLOUD_ACCOUNT={account}"])
        )


def test_from_file_rejects_any_other_account(tmp_path: Path) -> None:
    values = {**VALID_VALUES, "GCLOUD_ACCOUNT": "operator@example.com"}

    with pytest.raises(ProjectConfigError, match="huiliang@sgcodecampus.com"):
        ProjectConfig.from_file(_write_config(tmp_path, values=values))


def test_from_file_loads_the_canonical_contract(tmp_path: Path) -> None:
    config = ProjectConfig.from_file(_write_config(tmp_path))

    assert config == _project_config()


class RecordingRunner:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = iter(outputs)
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=next(self.outputs), stderr="")


def test_verify_gcloud_checks_exact_account_and_project_commands() -> None:
    runner = RecordingRunner(["huiliang@sgcodecampus.com\n", "sgcc-ai-experiments\n"])

    _project_config().verify_gcloud(runner=runner)

    expected_kwargs = {
        "check": True,
        "capture_output": True,
        "text": True,
        "shell": False,
    }
    assert runner.calls == [
        (
            [
                "gcloud",
                "config",
                "get-value",
                "account",
                "--configuration=ai-experiments",
            ],
            expected_kwargs,
        ),
        (
            [
                "gcloud",
                "config",
                "get-value",
                "project",
                "--configuration=ai-experiments",
            ],
            expected_kwargs,
        ),
    ]


@pytest.mark.parametrize(
    ("outputs", "expected_message"),
    [
        (["other@example.com\n"], "account"),
        (["huiliang@sgcodecampus.com\n", "some-other-project\n"], "project"),
    ],
)
def test_verify_gcloud_rejects_target_mismatches(
    outputs: list[str],
    expected_message: str,
) -> None:
    runner = RecordingRunner(outputs)

    with pytest.raises(TargetMismatchError, match=expected_message):
        _project_config().verify_gcloud(runner=runner)


@pytest.mark.parametrize(
    "overrides",
    [
        {"gcloud_configuration": "adept"},
        {"project_id": "adept-prod-497323"},
    ],
)
def test_verify_gcloud_rejects_adept_targets_before_calling_gcloud(
    overrides: dict[str, str],
) -> None:
    runner = RecordingRunner([])

    with pytest.raises(TargetMismatchError, match="Adept"):
        _project_config(**overrides).verify_gcloud(runner=runner)

    assert runner.calls == []


def test_cli_exits_zero_after_verifying_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = RecordingRunner(["huiliang@sgcodecampus.com\n", "sgcc-ai-experiments\n"])
    monkeypatch.setattr(config_module.subprocess, "run", runner)

    exit_code = config_module.main(
        ["--file", str(_write_config(tmp_path)), "--check-gcloud"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "target verified: sgcc-ai-experiments\n"
    assert captured.err == ""


def test_cli_exits_two_and_reports_target_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = RecordingRunner(["other@example.com\n"])
    monkeypatch.setattr(config_module.subprocess, "run", runner)

    exit_code = config_module.main(
        ["--file", str(_write_config(tmp_path)), "--check-gcloud"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "gcloud account mismatch" in captured.err
