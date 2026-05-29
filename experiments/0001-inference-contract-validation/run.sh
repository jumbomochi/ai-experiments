#!/usr/bin/env bash
# Convenience launcher for the 0001 smoke run.
# Assumes Ollama is up at http://localhost:11434 and qwen2.5:0.5b-instruct is pulled.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

uv run python -m shared.eval.runner.cli \
    --model "qwen2.5:0.5b-instruct" \
    --gold-set "smoke-v0.0" \
    --judge-config "v0.1" \
    --max-cost-usd 1.00 \
    --template-root experiments/0001-inference-contract-validation/prompt_templates \
    --experiment "0001-inference-contract-validation"
