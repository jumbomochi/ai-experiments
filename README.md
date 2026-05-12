# ai-experiments

A working repository for AI and local-LLM experiments — planning, code, and results in one place.

Started May 2026 with an initial ~3-month run; intended to keep growing.

## Layout

| Path | What's in it |
|------|--------------|
| `ROADMAP.md` | The current plan — what we're trying, in roughly what order. Living doc. |
| `EXPERIMENTS.md` | Index of every experiment with status and a one-line result. |
| `docs/planning/` | Planning documents — the source material the roadmap is distilled from. |
| `docs/notes/` | Cross-cutting notes, decisions, reading. |
| `docs/superpowers/specs/` | Design docs for non-trivial pieces of this repo. |
| `experiments/` | One folder per experiment — see [`experiments/README.md`](experiments/README.md). |
| `shared/` | Reusable Python: model loading, eval helpers, plotting, hardware reporting. |
| `scripts/` | Repo-level utilities. |
| `datasets/`, `models/` | Local data and weights. **Contents are git-ignored** — keep large files here. |

## Experiment areas

- **inference** — running models locally (Ollama, llama.cpp, vLLM, LM Studio, MLX), quantization, throughput/latency, context length.
- **finetuning** — LoRA/QLoRA and full fine-tunes, dataset prep, before/after evals.
- **rag** — embeddings, vector stores, chunking, retrieval quality.
- **agents** — agentic loops, tool/function calling, multi-agent, MCP, behavior evals.

## Environment

Managed with [uv](https://docs.astral.sh/uv/). Python ≥ 3.10.

```bash
uv sync                 # core, cross-platform deps
uv sync --extra dev     # + linting / notebooks
```

Heavy or platform-specific dependencies (CUDA `torch`, `vllm`, `bitsandbytes`, `mlx`/`mlx-lm`) are **not** in the root environment — add them per experiment with `uv add <pkg>` while working in that experiment, or in a per-experiment requirements file. This keeps `uv sync` working the same on macOS, a CUDA workstation, and cloud GPUs.

Quick hardware sanity check (handy to paste into an experiment's *Setup* section):

```bash
uv run python scripts/hardware_report.py
```

## Starting a new experiment

See [`experiments/README.md`](experiments/README.md) for the naming convention and the sections each experiment's README should have. Then add a row to `EXPERIMENTS.md` and link it from `ROADMAP.md`.
