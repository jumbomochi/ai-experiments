# Design — `ai-experiments` repository

**Date:** 2026-05-12
**Status:** Approved

## Purpose

A single working repository for AI and local-LLM experiments over an initial ~3-month run (starting May 2026), expected to keep growing long-term. It holds **planning, experiment code, and results together** — a code + experiments monorepo, not just a lab notebook and not just a code dump.

## Scope of experiments

Four areas, used as tags in experiment folder names:

- `inference` — local model serving (Ollama, llama.cpp, vLLM, LM Studio, MLX), quantization, throughput/latency, context length.
- `finetuning` — LoRA/QLoRA and full fine-tunes, dataset prep, before/after evals.
- `rag` — embeddings, vector stores, chunking, retrieval quality.
- `agents` — agentic loops, tool/function calling, multi-agent, MCP, behavior evals.

## Environment

- Python ≥ 3.10, dependency management with **uv**. `[tool.uv] package = false` — the repo is an environment + workspace, not a distributable package.
- Root environment holds only lean, cross-platform deps (`huggingface-hub`, `datasets`, `numpy`, `pandas`, `matplotlib`, `rich`, `python-dotenv`, `requests`) plus a `dev` extra (`ruff`, `pytest`, `ipykernel`, `jupyterlab`).
- Heavy / platform-specific deps (CUDA `torch`, `vllm`, `bitsandbytes`, `mlx`/`mlx-lm`) are **not** declared at the root — added per experiment, so `uv sync` works the same on macOS (dev), a CUDA workstation, and cloud GPUs. Hardware mix expected: Mac for dev/small runs, GPU box / rented cloud GPUs for heavy work; the repo stays portable across them.

## Layout

```
ai-experiments/
├── README.md                 # orientation + the layout table
├── ROADMAP.md                # living plan: Month 1/2/3 + backlog
├── EXPERIMENTS.md            # index table: ID · area · title · status · started · one-line result
├── pyproject.toml            # uv-managed; lean root deps + `dev` extra; package = false
├── .python-version           # 3.12
├── .gitignore                # ignores models/, datasets/, *.gguf/*.safetensors/*.pt, .venv/, outputs/, wandb/, .DS_Store, ...
├── docs/
│   ├── planning/             # source planning docs (raw input for the roadmap)
│   ├── notes/                # cross-cutting notes, decisions, reading
│   └── superpowers/specs/    # design docs (this file)
├── experiments/
│   └── README.md             # naming convention + the README sections each experiment must have
├── shared/
│   └── __init__.py           # reusable Python, promoted when used by >1 experiment
├── scripts/
│   └── hardware_report.py    # machine summary to paste into an experiment's Setup
├── datasets/.gitkeep         # contents git-ignored
└── models/.gitkeep           # contents git-ignored
```

## Conventions

- Experiment folders: `experiments/NNNN-<area>-<slug>/` — flat, chronological, area tag in the name (e.g. `0001-inference-ollama-quant-bench/`). Gaps in numbering are fine.
- Each experiment adds a row to `EXPERIMENTS.md` and a link from `ROADMAP.md`.
- Each experiment folder is self-contained: `README.md` (Hypothesis / Setup / Method / Results / Conclusion — write the first three before running), code/configs, `results/` (large artifacts git-ignored; commit small summaries like `metrics.json`).
- Record negative and inconclusive results too.
- No experiment template scaffolded (decided against for now); the conventions live in `experiments/README.md`. Revisit if copy-paste setup gets annoying.

## Hosting

- GitHub: `jumbomochi/ai-experiments`, **public**.
- Local clone at `/Users/huilianglui/GitHub/ai-experiments`; `origin` = `git@github-jumbomochi:jumbomochi/ai-experiments.git` (per the SSH-host-alias convention).

## Alternatives considered

- **Structured platform** — CI, pre-commit, devcontainer, per-area subpackages, eval-framework stubs upfront. Rejected as premature; add when there's a concrete need.
- **Docs-first** — just `docs/` + roadmap now, code layout later. Rejected; it's explicitly a code + experiments monorepo.

## Out of scope (for now)

CI/CD, pre-commit hooks, a devcontainer, a "new experiment" helper script, a LICENSE choice. Revisit as the repo matures.

---

## Update — 2026-05-12 (after reviewing the deep-research docs)

The two deep-research analyses in `docs/planning/` clarified the actual context:

- **Hardware:** the lab is anchored on an **NVIDIA DGX Spark (GB10, 128 GB unified memory)** with an **M4 Mac mini** as control plane / small-model baseline, occasional cloud burst, and a possible Mac Studio later (not critical path). This replaces the earlier "Mac for dev, GPU box for heavy" framing.
- **Areas:** `eval` and `memory` are promoted to first-class experiment areas — both research docs treat the evaluation harness and the agent-memory substrate as the spine of the quarter, not sub-cases of `agents`. Canonical area list is now `inference · eval · memory · finetuning · rag · agents`.
- **Scope:** the quarter is organized around four outcomes — a reproducible local eval lab, a calibrated judge service, a durable memory substrate, and one flagship pilot (a multilingual document analyst). Quantum, music transcription, and LinkedIn automation are explicit backlog. See `ROADMAP.md`.
- A "shared eval framework" is consequently no longer out of scope — it's the `eval` area's job.

Applied to `README.md`, `EXPERIMENTS.md`, and `experiments/README.md`.

---

## Update — 2026-05-14 (sovereignty + phase-based restructure)

Two further shifts after a deeper discussion of the eval system:

- **Sovereignty replaces "local"** as the design vocabulary. The eval substrate is anywhere we control the runtime and the data flow — Spark, Mac, *and* a measured GCE/EC2/Runpod box, all behind one OpenAI-compatible inference contract. Three tiers: **Tier 1** sovereign (the eval substrate; always-on + on-demand measured), **Tier 2** open-weights-as-service (excluded by default; revisited in a dedicated cost-benchmark phase), **Tier 3** closed-weights APIs (excluded; reserved at most for periodic recalibration on public gold-set subsets). The strategic objective is independence from proprietary state-of-the-art models. **Gold sets are the moat** — private, versioned, lane-organized, never shipped to a third-party API. The **sovereign judge stack** is the subscription-free engine that scores them.
- **Phase-based restructure** replaces the fixed 3-month timeline. AI-assisted dev cadence is uneven; calendar months are the wrong unit. `ROADMAP.md` is now organized around phases with goals, acceptance criteria, experiments, and a **mandatory documentation milestone** (long-form writeup + short-form post bundle) per phase. Three cross-cutting tracks — **Instrumentation, Dashboards, Communications** — run alongside the phases. A late phase (Phase 8) quantifies sovereign vs Tier 2 cost.

New directories: `docs/writeups/` (long-form drafts), `docs/social/` (short-form drafts). Layout table in `README.md` updated. Hardware section in `README.md` renamed to *Sovereignty & compute* with the tier breakdown.
