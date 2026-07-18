"""CLI for the eval runner.

Examples:
    uv run python -m shared.eval.runner.cli \\
        --model qwen2.5:0.5b-instruct \\
        --gold-set smoke-v0.0 \\
        --judge-config v0.1 \\
        --max-cost-usd 1.00 \\
        --template-root experiments/0001-inference-contract-validation/prompt_templates \\
        --experiment 0001-inference-contract-validation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.eval.runner.runner import run_campaign


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
