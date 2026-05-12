# Roadmap

Living document. Distilled from the two deep-research analyses in `docs/planning/` (2026-05-12), starting May 2026. Reorder, drop, add freely. Each item becomes an `experiments/NNNN-<area>-<slug>/` folder when work on it starts; statuses mirror `EXPERIMENTS.md`.

## Guiding principle

**Build the evaluation factory first**, then layer on memory, localization, and one or two real pilots. Resist framework sprawl, and resist doing all the ideas at once — anything that doesn't move one of the quarter's four outcomes is backlog, not current work.

**End-of-quarter "done" state:**

- Onboard a new model and run the full suite without touching framework code.
- ≥ 5 evaluation lanes: general · SEA languages · Japanese · OCR/VLM · finance.
- Judge stack has a standing human-calibration set and explicit bias checks.
- Memory system can resume from checkpoints, retrieve long-term state, and replay prior runs.
- One pilot application that proves the stack is more than a benchmark collection.

## Hardware context

- **DGX Spark (GB10, 128 GB unified memory)** — compute anchor: blessed local runtime, fine-tuning, large-model inference.
- **M4 Mac mini** — control plane, dataset prep, dashboards, small-model baseline (MLX / mlx-lm / vLLM-Metal).
- **Cloud burst** (GCE A3 · AWS P5 · neoclouds) — high-throughput batch or final fine-tune epochs only; mind egress; pin storage to Singapore regions (`ap-southeast-1` / `asia-southeast1`).
- **Mac Studio** — TBD, not on the critical path. Revisit after Month 2 if the Mac lane is measurably the bottleneck.

---

## Month 1 — May 2026 · Foundation: platform + first eval loop

- [ ] **`inference`** — Pick one blessed local runtime on the DGX Spark behind a standard HTTP completions endpoint (NIM or TensorRT-LLM via the official container path) + one challenger runtime for experimentation (vLLM or SGLang via Dynamo). Goal: every model invocable through the same endpoint shape, whether on the Spark, the Mac baseline, or a later cloud burst.
- [ ] **`eval`** — First evaluation loop: `lm-evaluation-harness` for deterministic / regression benchmarks + `Inspect AI` for agentic / multimodal / tool-use evals. Every run logs prompts, outputs, timings, artifacts.
- [ ] **`eval`** — Curate a gold set of ~250–400 examples split across: general reasoning · SEA-language tasks · Japanese tasks · OCR/document tasks · finance.
- [ ] **`memory`** — Stand up Postgres + pgvector. Define the model-manifest schema (model · prompt version · checkpoint id · memory namespace · artifact refs · tool trace) that makes a run reproducible without hidden prompt state.
- [ ] **`eval`** — Stand up a small baseline judge (deterministic / executable scoring where ground truth exists) and wire it into the loop.

## Month 2 — June 2026 · Judges, memory kernel, localization

- [ ] **`eval`** — Three judge modes: deterministic/executable · pairwise · rubric (factuality / evidence use / locale appropriateness / OCR fidelity / numeric consistency scored separately). Add answer-order randomization, judge-swap tests, monthly human calibration (target Cohen's κ ≥ 0.8).
- [ ] **`eval`** — Judge-of-the-judge: stress every deployed judge on order-swapped pairs, length-controlled variants, and adversarially similar responses (JudgeBench-style) before trusting it in the loop.
- [ ] **`memory`** — Memory kernel: thread checkpoints, long-term namespaces (user / project / task), artifact layer (PDFs, OCR outputs, tables), eval-trace layer. Provenance on every write; online retrieval/write during sessions + offline nightly consolidation (summarize, dedupe, contradiction handling).
- [ ] **`memory`** — Memory security from day one: write-path validation, scoped retrieval by principal/project, rollback points, forget/delete semantics. Decide here: **Mem0 v1.0** (vector + knowledge graph) vs. a thinner LangGraph-style checkpoint/namespace stack — record the decision and its rationale in `docs/notes/`.
- [ ] **`rag`** — SEA localization lane: deploy SEA-LION v4 (and MERaLiON if speech is in scope) locally; evaluate on SEA-HELM / SeaExam / SeaBench. Confirm "multilingual on translated data" ≠ useful regional performance.
- [ ] **`inference` + `eval`** — Japanese lane: Swallow LLM for Japanese reasoning/math via `llm-jp-eval`; JFinQA for Japanese financial numerical reasoning; JAMMEval for multimodal (OCR, doc QA, charts/tables, culture-aware VQA).
- [ ] **`rag` + `eval`** — OCR / VLM lane: dots.ocr / PaddleOCR 3.0 / Nougat baselines; benchmark on SEA-Vision, JaWildText, JAMMEval, CC-OCR v2 — especially vertical Japanese text and degraded scans.
- [ ] **`eval`** — Finance lane: FinanceBench (open-book filing QA) · FinQA / TAT-QA (numerical + hybrid table-text) · ConvFinQA (multi-turn) · JFinQA. Separates retrieval / arithmetic / grounding / temporal consistency / follow-up quality.

## Month 3 — July 2026 · Productionize + flagship pilot

- [ ] **`agents` (pilot)** — **Multilingual document analyst** (primary pilot): Japanese + SEA OCR → grounded document QA → financial reasoning. Exercises localization, VLM/OCR, evidence-grounded judging, and memory/context transfer in one application.
- [ ] **`eval`** — Productionize the lab: nightly/weekly regression runs, a leaderboard view, Singapore-pinned storage policy, and one replay test proving a run resumes from stored state (not a handcrafted prompt).
- [ ] **`agents` (stretch pilot)** — Second pilot: educational tutor (e.g. Primary-4-appropriate, MOE-style guardrails — supervised, interaction limits, prompts that encourage evaluation over answer-getting). Chosen over social-content automation because tutoring compounds with the memory + eval work already built.

## Backlog (deliberately not this quarter)

- LinkedIn / social-content automation agent.
- Quantum simulation work (cuQuantum — state vector, tensor network, QEC).
- Music / guitar pedagogy: Automatic Music Transcription (MT3, MusicFM, Basic Pitch) → MIDI / sheet feedback.
- Hyperscaler cost-optimization deep dive (reserved vs. spot vs. neoclouds, egress modeling).
- Mac Studio purchase + tri-tier architecture finalization.
- Full LoRA / QLoRA fine-tuning track beyond what the pilots require.
- Broader hyperscaler comparison / multi-cloud orchestration platform.

## Open questions

- Blessed local runtime: NIM vs. TensorRT-LLM vs. vLLM as the *default* (not just the challenger)?
- Memory stack: Mem0 v1.0 (vector + KG) vs. a thin LangGraph-style checkpoint/namespace layer — what's the deciding test?
- Judge model: a local model as judge vs. cloud GPT-4o / Claude — and how does Singapore data residency constrain that?
- Default cloud burst target (region + provider), given egress costs and PDPC comparable-protection?
- Does the M4 Mac mini have headroom to be both control plane *and* small-model baseline, or does that need splitting?
