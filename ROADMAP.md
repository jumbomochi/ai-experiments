# Roadmap

Living document. Distilled from the two deep-research analyses in `docs/planning/` (2026-05-12); refined on 2026-05-14 to (a) center on **sovereignty + gold sets** as the eval substrate, and (b) restructure to a **phase-based** model with documentation as a first-class deliverable (no fixed timeline). Started May 2026, open-ended. Reorder, drop, add freely. Each experiment in a phase becomes an `experiments/NNNN-<area>-<slug>/` folder when work on it starts; statuses mirror `EXPERIMENTS.md`.

## Guiding principle

**Build a sovereign evaluation lab first** — one we own end-to-end, where any newly released open-weight model can be ranked on our private gold sets within an hour, judged by sovereign judges, with cost discipline enforced. Memory, localization, and a flagship application layer on top. Resist framework sprawl, and resist doing all the ideas at once — anything that doesn't move one of the end-state outcomes below is backlog, not current work.

The strategic objective is **independence from proprietary state-of-the-art models**. **Gold sets are the moat** — private, versioned, lane-organized, never shipped to a third-party API. The **sovereign judge stack** is the subscription-free engine that scores them.

**Comprehensiveness over speed.** No fixed quarter — each phase is "done" when its acceptance criteria pass and its documentation milestone is published. AI-assisted development cadence is wildly uneven; calendar months are the wrong unit of planning.

## End-state outcomes (when the lab is mature)

- Onboard any newly-released open-weight model on any sovereign deployment target and produce a comparable score on every gold-set lane within ~1 hour, no framework code changes.
- ≥ 5 gold-set lanes — general reasoning · SEA languages · Japanese · OCR/VLM · finance — each privately curated, versioned, and lane-owned.
- Sovereign judge stack (local generalist + local specialist + deterministic where ground truth exists) with documented bias checks and a human-calibration set (Cohen's κ ≥ 0.8). Closed-API judges used at most for periodic external recalibration on *public* gold-set subsets.
- Cost discipline: every eval campaign declares a budget, auto-tears-down measured compute, logs cost alongside score. Singapore-region pinning enforced for sovereign on-demand targets.
- Quantified comparison of sovereign deployment cost vs Tier 2 (Fireworks, Together, Groq, …) for representative models and workloads.
- Memory system can resume from checkpoints, retrieve long-term state, and replay prior runs.
- One flagship application built on top of the lab (e.g., the multilingual document analyst) demonstrating the lab supports real work.
- A public body of writing + dashboards: long-form articles per phase, short-form posts, and a public-facing leaderboard view.

## Sovereignty & compute

The eval substrate is **sovereign compute** — anywhere we control the runtime and the data flow. Physical location doesn't matter; control does. A model running inside a measured EC2 VM with our container is no less sovereign than the same model on the Spark. The opposite isn't "in the cloud" — it's **API-as-service**.

**Tier 1 — sovereign deployment targets (the eval substrate):**

*Always-on (owned silicon):*

- **DGX Spark (GB10, 128 GB unified memory)** — compute anchor: blessed sovereign runtime, fine-tuning, large-model inference, sovereign judge service.
- **M4 Mac mini** — control plane, dataset prep, dashboards, small-model baseline (MLX / mlx-lm / vLLM-Metal).

*On-demand (measured rental, never always-on):*

- **GCE A3 · AWS P5 · neoclouds (Runpod, Lambda, Vast)** — for models that don't fit on the Spark, or for parallel runs. Spin up → run campaign → spin down. Spot/preemptible by default; declared budget; auto-teardown; pinned to Singapore regions (`ap-southeast-1` / `asia-southeast1`).

**Tier 2 — open-weights-as-service** (Together, Fireworks, Groq, Bedrock-Llama, HF Inference Endpoints): open weights but third-party runtime. *Excluded from the default eval substrate*; integrated only in **Phase 8** for the explicit cost-comparison benchmark, on *public* gold-set subsets only.

**Tier 3 — closed-weights APIs** (OpenAI, Anthropic, Gemini, Bedrock-Claude): no weights, no portability. *Excluded from the eval substrate*. Reserved at most for one narrow role — periodic external recalibration of the sovereign judge stack — and only against *public* gold-set subsets so private data never leaves sovereign tenancy.

**Mac Studio** — TBD; not on the critical path. Revisit if the Mac lane is measurably the bottleneck.

## Operating model

The roadmap is **phase-based**, not time-based. Phases are completed in roughly the dependency order shown below, but several can run in parallel once Phase 1 is up (e.g., gold-set curation alongside the inference substrate, or memory alongside lane depth).

Each phase has:

- **Goal** — what insight or capability is unlocked when this is complete.
- **Acceptance criteria** — specific, testable conditions for "done."
- **Experiments** — the `experiments/NNNN-<area>-<slug>/` folders that comprise this phase.
- **Documentation milestone** — one long-form technical writeup + a short-form post bundle (LinkedIn primary; X / Bluesky / Mastodon as needed). Drafts live in `docs/writeups/` and `docs/social/`; published URLs are recorded back in the drafts. **Documentation completion is part of "phase done."**
- **Status** — `planned` · `in progress` · `complete`, with `started` and `completed` timestamps as the phase changes state.

Three **cross-cutting tracks** run alongside the phases — see the bottom of this document:

- **Instrumentation** · what gets logged per run, schema evolution, retention.
- **Dashboards** · internal first, public-facing leaderboard from Phase 6.
- **Communications / outreach** · the writeup-and-post cadence + recurring threads.

---

## Phase 1 — Sovereign inference substrate

**Status:** in progress (started 2026-05-27; rebaselined 2026-07-18). The Mac substrate is implemented and was validated by experiment `0001-inference-contract-validation`. GCP Terraform and model manifests are scaffolded but have not yet produced a preserved live campaign. Replay under the current schema, private-tunnel cloud execution, and automatic teardown are still required.

**Goal:** Any sovereign deployment target (Spark, Mac, measured cloud burst) exposes the same OpenAI-compatible endpoint. Every eval run is reproducible from stored state, with a tracked cost budget.

**Acceptance criteria:**

- The same gold-set example can be scored against a model on the Spark, on the Mac, and on a measured GCE / EC2 / Runpod box, by hitting one URL pattern that differs only in host.
- A randomly chosen past run can be fully reconstructed from stored state — no handcrafted prompts.
- Every eval run records its cost; campaigns that exceed `max_cost_usd` halt and tear down on-demand compute automatically.

**Experiments:**

- `0001-inference-contract-validation` — Mac inference contract, run store, deterministic judge, and runner smoke; complete, pending current-schema rerun evidence.
- `inference-blessed-sovereign-runtime` — choose and commission the default Spark runtime after the hardware arrives.
- `inference-private-cloud-smoke` — validate the same contract on a measured GCP L4 target through an SSH tunnel.
- `eval-run-storage-replay` — reconstruct a randomly selected preserved run from stored state.
- `eval-cost-discipline-teardown` — prove budget halting and automatic destruction of on-demand compute.

**Documentation milestone:** *Writeup* — "Building a sovereign LLM inference substrate: DGX Spark, M4 Mac, and measured cloud burst behind one endpoint." *Short-form bundle* — a thread on why sovereign-by-default and what it costs to start.

---

## Phase 2 — Gold sets v0.1

**Status:** in progress (started 2026-07-11; rebaselined 2026-07-18). The Argilla choice, seed schema, curation CLI, five lane directories, and GCP annotation workspace are implemented. Only 10 candidate seeds exist, no reviewed `annotated.jsonl` exists, and `v0.1` has not been released.

**Goal:** Five lane-organized, versioned, *private* gold sets exist; the curation workflow is documented and repeatable; provenance is tracked per example.

**Acceptance criteria:**

- ~250–400 examples in `gold-set v0.1`, split across general reasoning · SEA languages · Japanese · OCR/VLM · finance.
- Each example has: stable ID · lane · source · annotator · date · correct-answer or rubric · provenance tag · "never to third-party API" flag.
- The curation pipeline (seed → expand → filter → annotate → review → release) is documented and a fresh contributor can use it to add an example.
- Gold-set versioning works: `v0.1` is immutable; adds go to `v0.2`.

**Experiments:**

- `eval-curation-workflow` — stand up the seed → expand → filter → annotate → review pipeline.
- `eval-annotation-tooling` — validate the selected Argilla v2 workflow on a small lane; document setup and operator friction.
- `eval-versioning-schema` — gold-set versioning, contamination tagging, public/private split.
- `eval-gold-set-v0.1` — first ~250–400 examples across 5 lanes; lane owners identified.

**Documentation milestone:** *Writeup* — "Gold sets as the moat: a private-eval curation workflow for the contamination era." *Short-form bundle* — what makes a gold-set example good; provenance-first principles.

---

## Phase 3 — Sovereign judge stack

**Status:** in progress (started 2026-07-11; rebaselined 2026-07-18). Rubric routing, judge persistence, a Qwen 2.5 72B manifest, and an uncalibrated v0.2 bundle exist in code. No live sovereign-judge campaign, specialist bake-off, human calibration set, kappa gate, or bias stress result exists yet.

**Goal:** A judge stack that runs entirely on sovereign compute, is human-calibrated to Cohen's κ ≥ 0.8 on its assigned tasks, and has documented bias profiles.

**Acceptance criteria:**

- Specialist judge (Prometheus 2 8×7B or Atla Selene) + generalist judge (Qwen 2.5 72B Instruct or Llama 3.3 70B Instruct) + deterministic scoring are all deployed behind the inference contract.
- A 100–200-example human-calibration set exists, double-annotated, with inter-annotator agreement measured.
- Each judge has a κ score per task type; only κ ≥ 0.8 judges are trusted for production scoring.
- Judge-of-the-judge stress tests pass (position bias, length bias, JudgeBench-style discrimination) above documented thresholds.

**Experiments:**

- `eval-specialist-judge-bake-off` — Prometheus 2 vs Atla Selene on representative tasks.
- `eval-generalist-judge-bake-off` — Qwen 2.5 72B Instruct vs Llama 3.3 70B Instruct.
- `eval-human-calibration-set` — build the 100–200 examples, double-annotate, measure agreement.
- `eval-judge-bias-stress` — position / length / discrimination tests; document thresholds.

**Documentation milestone:** *Writeup* — "Calibrating a sovereign LLM-as-judge stack: methods, biases, what we trust." *Short-form bundle* — case studies of where judges fail.

---

## Phase 4 — Lane depth

**Status:** planned.

**Goal:** Each of the five lanes is deepened with domain-specific benchmarks, lane-specific rubrics, and a meaningful body of evaluated models per lane.

**Acceptance criteria:**

- **SEA lane:** SEA-LION v4 deployed and evaluated on SEA-HELM / SeaExam / SeaBench; lane-specific rubric documented.
- **Japanese lane:** Swallow LLM evaluated via `llm-jp-eval`; JFinQA + JAMMEval scores recorded; lane-specific rubric documented.
- **OCR/VLM lane:** dots.ocr, PaddleOCR 3.0, Nougat baselines evaluated on SEA-Vision, JaWildText, JAMMEval, CC-OCR v2; vertical-text and degraded-scan sub-lanes characterized.
- **Finance lane:** FinanceBench, FinQA, TAT-QA, ConvFinQA, JFinQA all wired; per-lane failure mode (retrieval vs arithmetic vs grounding vs temporal vs follow-up) attributable.

**Experiments:**

- `rag-sea-lion-sea-helm` — SEA lane deepening.
- `inference-japanese-swallow-llm-jp-eval` — Japanese lane deepening.
- `rag-ocr-vlm-multi-baseline` — OCR / VLM lane deepening.
- `eval-finance-multi-benchmark` — finance lane deepening.

**Documentation milestone:** *Writeups* — one technical post per lane (4 total) + a cross-lane comparison post. *Short-form bundle* — surprising findings per lane.

---

## Phase 5 — Long-term memory substrate

**Status:** planned.

**Goal:** A long-term agent memory substrate is chosen by evidence (not by paper-survey vibe), wired behind the `shared/memory/` adapter, with governance implemented once at the adapter level.

**Acceptance criteria:**

- LangGraph adopted as orchestration; Postgres-backed checkpointer running.
- Adapter interface in `shared/memory/` exposes `write` · `recall_semantic` · `recall_entity` · `traverse` · `snapshot` · `restore`.
- Two backends implemented and bake-off run: **A** (Postgres + Apache AGE + pgvector) vs **C** (Neo4j 5.x with native vector indexes).
- Bake-off task — entity-centric retrieval + multi-hop reasoning on a JFinQA / FinanceBench subset with an injected temporal contradiction (a superseding filing) — has a clear winner with rationale documented in `docs/notes/memory-backend.md`.
- Governance (write-path validation, scoped retrieval, rollback, forget/delete, provenance) implemented once at the adapter level; both backends inherit it.

**Experiments:**

- `memory-langgraph-checkpointer` — LangGraph + Postgres checkpointer + model-manifest schema.
- `memory-adapter-interface` — `shared/memory/` interface definition + test harness.
- `memory-backend-bake-off` — A vs C on JFinQA-with-contradiction.
- `memory-governance-layer` — adapter-level governance + threat model entries.

**Documentation milestone:** *Writeup* — "Postgres + AGE + pgvector vs Neo4j as long-term agent memory: a bake-off." *Short-form bundle* — what makes a graph DB worth the operational cost.

---

## Phase 6 — Sovereign Eval Lab v1

**Status:** planned.

**Goal:** The lab as a product. Drop a model name in; get a full scorecard against every prior model in the leaderboard. One hour, under budget, sovereign.

**Acceptance criteria:**

- Given a model name and target deployment, the lab runs the full gold-set suite, judges it sovereignly, logs cost and score, ranks it on the leaderboard — in under 1 hour and under a declared `max_cost_usd`.
- Public-facing read-only leaderboard view live on the Mac mini (lanes × models, drill-down to per-example results, judge traces, model output).
- Internal dashboards: judge agreement (κ over time), run latencies p50/p95, cost-per-eval, gold-set growth, regression vs designated baseline.
- Replay test passes on a randomly chosen historical run.
- Nightly or weekly regression on a designated baseline model, with alerts when something moves.

**Experiments:**

- `eval-end-to-end-onboarding` — proves the one-hour acceptance criterion end-to-end.
- `eval-leaderboard-dashboard` — read-only public view on the Postgres run-store.
- `eval-internal-metrics-dashboard` — judge agreement, latencies, costs over time.
- `eval-regression-alerts` — automated baseline regression with alerts.

**Documentation milestone:** *Writeup* — "Sovereign Eval Lab v1: what it does, what it costs, how it ranks the open models of 2026." *Short-form bundle* — the leaderboard launch thread; selected surprises; cross-lane comparisons. *Headline artifact:* the public leaderboard itself.

---

## Phase 7 — Flagship application: multilingual document analyst

**Status:** planned.

**Goal:** A real application built on the lab — Japanese + SEA OCR → grounded document QA → financial reasoning — demonstrating the lab supports practical work, not just benchmarking.

**Acceptance criteria:**

- The application uses the same inference contract, gold sets (or extensions thereof), judges, and run-storage as the rest of the lab.
- A documented "application gold set" extends the Japanese, OCR/VLM, and finance lanes with end-to-end scenarios.
- Demo flow: feed it a multilingual filing pack → grounded answers with citations → judged by the sovereign stack.

**Experiments:**

- `agents-document-analyst-mvp` — minimum viable end-to-end flow.
- `agents-document-analyst-grounding` — citation faithfulness, evidence checks.
- `eval-application-gold-set` — extends Phase-4 lanes with end-to-end application scenarios.

**Documentation milestone:** *Writeup* — "Building a multilingual document analyst on a sovereign stack." *Short-form bundle* — annotated demos with screen recordings.

---

## Phase 8 — Sovereign vs Tier 2 cost benchmark

**Status:** planned.

**Goal:** Quantify the actual economic comparison of sovereign deployment vs open-weights-as-a-service (Tier 2) for representative models and workloads. Inform when sovereignty is the cheaper choice and when a Tier-2 endpoint actually wins on $/judgment or latency.

**Acceptance criteria:**

- The eval runner can target a Tier-2 endpoint through the same inference contract (one-time integration).
- A representative open-weight model (e.g. Llama 3.3 70B Instruct or Qwen 2.5 72B Instruct) is benchmarked on a *public* gold-set subset on:
  - DGX Spark (sovereign, always-on)
  - Measured GCE / EC2 / Runpod (sovereign, on-demand spot)
  - Fireworks / Together / Groq (Tier 2)
- Output: a cost report with $/judgment, latency p50/p95, and a break-even analysis (at what volume does sovereign-on-demand beat Tier 2? when does always-on Spark amortize?).
- Private gold sets are *not* used in this phase (no leakage); only public subsets.

**Experiments:**

- `eval-tier2-integration` — Fireworks / Together / Groq behind the inference contract.
- `eval-sovereign-vs-tier2-cost` — the actual benchmark + report.

**Documentation milestone:** *Writeup* — "What sovereign actually costs (and when Fireworks wins)." *Short-form bundle* — the headline numbers with reproducibility receipts.

---

## Phase 9 — Stretch applications

**Status:** planned (low priority — pulled forward only if it serves an immediate need).

**Goal:** Additional applications on top of the lab, starting with an educational tutor (Primary-4-appropriate, MOE-style guardrails).

**Acceptance criteria:** Each application reuses the inference contract, gold sets, judges, dashboards.

**Experiments:**

- `agents-educational-tutor` — Primary-4 tutor with MOE-style guardrails.
- _… other applications as they justify themselves._

**Documentation milestone:** One short writeup per application + a short-form post.

---

## Cross-cutting tracks

### Instrumentation

What gets logged per run, retained how long, in what schema. Starts in Phase 1 with the `run` schema; evolves as new phases add new fields — judge traces in Phase 3, memory operations in Phase 5, application traces in Phase 7. Schema changes are migrations on the Postgres instance and tracked in `docs/notes/instrumentation.md`.

### Dashboards

Hosted on the Mac mini; data lives in the Postgres instance shared with LangGraph and the run-store.

- **Internal (Phase 2 onward):** gold-set growth over time, run latencies p50/p95, cost-per-eval, judge agreement κ trend, regression deltas vs baseline.
- **Public-facing (Phase 6 onward):** the leaderboard view — lanes × models scorecard, drill-down to per-example results, judge traces, model output. Singapore-pinned storage.

Stack candidates (decide in Phase 6): Grafana on Postgres (fast, opinionated) vs a custom Next.js dashboard on the Postgres run-store (more design control, more code).

### Communications / outreach

Documentation is not optional — it's part of "phase done."

**Publication pattern (decided 2026-05-14):** **Substack canonical + HubSpot (SG Code Campus) excerpt-and-link.** Substack carries the full article (preserving the newsletter / Notes / recommendations mechanic that the technical-builder audience reads); the HubSpot company site carries a short excerpt + link back, with a bio tying the author to SG Code Campus. The repo `docs/writeups/` stays the markdown source of truth.

Each phase produces:

- **One long-form technical writeup** — drafted in `docs/writeups/phase-N-<slug>.md`, published canonical on Substack, excerpted on HubSpot with a "read the full deep dive on `<Substack>`" link. Both URLs recorded in the draft's front-matter.
- **Short-form post bundle** — LinkedIn primary; X / Bluesky / Mastodon (and Substack Notes) as the technical-builder audience warrants. Drafted in `docs/social/phase-N-<slug>.md`. Mix of teaser, headline result, and call-to-engage threads. Each short-form post links to the Substack canonical.

Plus **recurring cadence** layered on top:

- **Monthly retrospective thread** — what shipped, what surprised us, what's next.
- **Model-of-the-month leaderboard update** — once Phase 6 ships the public leaderboard, a recurring post highlighting newly evaluated open models.
- **Reading lists / paper threads** — when something from the field directly informs a lab decision.

---

## Backlog (deliberately not yet)

- LinkedIn / social-content **automation agent**. (Note: short-form posts about the lab are part of the Communications track and are written by hand. An *automated* content agent is separate, and not on the path.)
- Quantum simulation work (cuQuantum — state vector, tensor network, QEC).
- Music / guitar pedagogy: Automatic Music Transcription (MT3, MusicFM, Basic Pitch) → MIDI / sheet feedback.
- Hyperscaler cost-optimization deep dive (reserved vs spot vs neoclouds, multi-region egress modeling) — partially absorbed into Phase 8 for the eval-relevant subset.
- Mac Studio purchase + tri-tier architecture finalization.
- Full LoRA / QLoRA fine-tuning track beyond what the applications require.
- Broader hyperscaler / multi-cloud orchestration platform.

---

## Open questions

- Blessed **sovereign runtime** on the Spark: NIM vs. TensorRT-LLM vs. vLLM as the *default* (not just the challenger)?
- **Sovereign judge models**: specialist — Prometheus 2 (8×7B) vs. Atla Selene? Generalist — Qwen 2.5 72B Instruct vs. Llama 3.3 70B Instruct? Phase-3 bake-offs decide; quarterly review thereafter.
- **External recalibration**: do we use *any* closed-API judge at all for periodic sanity checks (only on public gold-set subsets), or is the sovereignty cleaner if we exclude them fully? Working bias: exclude unless drift actually shows up.
- **Default GCP burst configuration**: which machine type, GCP region/zone, and Spot VM policy give the best economics while meeting Singapore residency and availability constraints?
- **Memory backend bake-off** (Phase 5): A (Postgres + AGE + pgvector) vs C (Neo4j 5.x).
- **LangGraph `Store`** adoption: as-is vs wrapped behind our adapter?
- **Mac mini headroom**: enough as both control plane *and* small-model baseline + dashboard host, or split?
- **Dashboard stack** (Phase 6): Grafana on Postgres vs a custom Next.js app on the run-store?
- **Substack name & URL** — decided this week. Long-term-durable, not topic-locked to sovereign AI evals. Track in PLAN.md Open Items.
