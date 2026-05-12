# Experiments

One folder per experiment. Flat and chronological, with the area tag in the name:

```
experiments/NNNN-<area>-<slug>/
```

- `NNNN` — zero-padded sequence number (`0001`, `0002`, …). Just take the next integer; gaps are fine.
- `<area>` — one of `inference`, `eval`, `memory`, `finetuning`, `rag`, `agents`.
- `<slug>` — short kebab-case description.

Examples:

```
0001-inference-dgx-blessed-runtime/
0002-eval-first-harness-loop/
0003-memory-pgvector-kernel/
0004-rag-sea-lion-sea-helm/
```

When you create one, add a row to [`../EXPERIMENTS.md`](../EXPERIMENTS.md) and link it from [`../ROADMAP.md`](../ROADMAP.md).

## What goes in an experiment folder

- `README.md` — the writeup (sections below). Write the first three sections **before** running anything.
- code / configs / notebooks for the experiment.
- `results/` — outputs, metrics, plots, logs. Large artifacts are git-ignored (see the repo `.gitignore`); commit small summary files like `metrics.json` or a results table.

### README sections

1. **Hypothesis** — what you expect and why. One or two sentences.
2. **Setup** — models, hardware, datasets, key versions/params. Enough to reproduce. (`uv run python ../../scripts/hardware_report.py` for the machine details.)
3. **Method** — what you actually did: commands, configs, steps.
4. **Results** — numbers, tables, plots. What happened.
5. **Conclusion** — was the hypothesis supported? What you'd do next; link follow-up experiments.

Keep it honest — negative and inconclusive results are still results; record them.

## Shared code

Reusable helpers (model loading, eval scaffolding, plotting, hardware reporting) live in [`../shared/`](../shared/). Import with `from shared import ...`, running from the repo root (or via `uv run`). Promote anything you copy-paste a second time.
