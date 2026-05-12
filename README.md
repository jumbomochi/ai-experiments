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

- **inference** — running models (DGX Spark local runtime via NIM / TensorRT-LLM / vLLM / SGLang; Mac via MLX / mlx-lm / vLLM-Metal), quantization, throughput/latency, context length, standard serving endpoints.
- **eval** — evaluation harnesses (lm-evaluation-harness, Inspect AI), gold sets, LLM-as-judge (deterministic / pairwise / rubric), judge-of-the-judge bias checks, regression runs, leaderboards.
- **memory** — agent memory: thread checkpoints, long-term namespaces, artifact stores, retrieval, offline consolidation, memory security, replay.
- **finetuning** — LoRA / QLoRA and full fine-tunes, dataset prep, before/after evals.
- **rag** — embeddings, vector stores, chunking, retrieval quality; localization lanes (SEA-LION / SEA-HELM, Japanese llm-jp-eval, OCR/VLM).
- **agents** — agentic loops, tool/function calling, multi-agent, MCP, pilot applications, behavior evals.

Canonical order — also used in `EXPERIMENTS.md` and experiment folder names: `inference · eval · memory · finetuning · rag · agents`.

## Hardware

- **DGX Spark (GB10, 128 GB unified memory)** — compute anchor: blessed local runtime, fine-tuning, large-model inference.
- **M4 Mac mini** — control plane, dataset prep, dashboards, small-model baseline (MLX / mlx-lm / vLLM-Metal).
- **Cloud burst** (GCE A3 · AWS P5 · neoclouds) — high-throughput batch or final fine-tune epochs only; mind egress, pin storage to Singapore regions (`ap-southeast-1` / `asia-southeast1`).
- **Mac Studio** — TBD, not on the critical path; revisit after Month 2 if the Mac lane is measurably the bottleneck.

Run `uv run python scripts/hardware_report.py` on any of these and paste the output into an experiment's *Setup* section so runs stay comparable.

## Environment

Managed with [uv](https://docs.astral.sh/uv/). Python ≥ 3.10.

```bash
uv sync                 # core, cross-platform deps
uv sync --extra dev     # + linting / notebooks
```

Heavy or platform-specific deps (CUDA `torch`, `vllm`, `bitsandbytes`, `mlx` / `mlx-lm`, NIM / TensorRT-LLM, …) are **not** in the root environment — add them per experiment with `uv add <pkg>`, or in a per-experiment requirements file. This keeps `uv sync` consistent across the Mac, the DGX Spark (ARM + CUDA), and cloud GPUs.

## Starting a new experiment

See [`experiments/README.md`](experiments/README.md) for the naming convention and the sections each experiment's README should have. Then add a row to `EXPERIMENTS.md` and link it from `ROADMAP.md`.
