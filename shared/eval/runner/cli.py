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


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--gold-set", required=True, dest="gold_set_version")
    p.add_argument("--judge-config", required=True, dest="judge_config_version")
    p.add_argument("--max-cost-usd", type=float, required=True)
    p.add_argument("--template-root", required=True, type=Path)
    p.add_argument("--experiment", default=None, dest="experiment_id")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()

    rr = run_campaign(
        model_id=args.model,
        gold_set_version=args.gold_set_version,
        judge_config_version=args.judge_config_version,
        max_cost_usd=args.max_cost_usd,
        template_root=args.template_root,
        experiment_id=args.experiment_id,
        test=args.test,
    )
    print(f"run_id={rr.run_id} status={rr.status} "
          f"cost=${rr.cost_actual_usd:.6f} "
          f"scored={rr.n_examples_scored} errored={rr.n_examples_errored}")
    sys.exit(0 if rr.status == "completed" else 1)


if __name__ == "__main__":
    _cli()
