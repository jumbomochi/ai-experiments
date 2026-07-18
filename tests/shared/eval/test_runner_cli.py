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
