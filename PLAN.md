# Execution Plan v1

Live calendar / execution doc. `ROADMAP.md` is the strategy reference (what & why); this is the tactical layer (when, in what order, at what depth per week). Edit freely as reality diverges from the plan — that's what living planning docs are for.

**Version:** v1.1 — drafted 2026-05-14, revised 2026-05-26 (absorbed a one-week slip; see Revision log)
**Start date:** Monday 2026-05-25 (was 2026-05-18 — slipped one week)
**Coverage:** ~24 weeks, through end of Phase 8 (target first week of November 2026); Phase 9+ open-ended.

## Revision log

- **2026-05-26 — one-week slip absorbed (v1 → v1.1).** Week 1's substrate/curation work (the May 18–24 block) didn't happen, so the entire calendar shifts +1 week: new start **Mon 2026-05-25**, end-of-Phase-8 target moves from end-October to **~first week of November 2026**. **The DGX Spark order was placed on the original schedule (week of 2026-05-18), ETA ~Jun 15 — it does _not_ shift.** Useful side effect: with everything else +1 week, the Spark now lands right at the **start** of S2 (Mon 2026-06-15) instead of mid-sprint, de-risking the bring-up.

## Inputs & assumptions

| Input | Value | Confidence |
|---|---|---|
| Allocation | ~30–40% of work time → **~13–14 hr/week average** (1 focus day ≈ 7 hr + 2–3 evenings ≈ 2 hr each) | High |
| Start date | Monday 2026-05-25 (was 2026-05-18; slipped one week) | Locked |
| M4 Mac mini | Operational from day one (16 GB unified memory) | High |
| **DGX Spark** | **Ordered on schedule (week of 2026-05-18); arrival ETA ~Jun 15.** Did not slip with the rest of the calendar. | **Med — chase ETA by week 3** |
| Public holidays / blocked weeks | TBD — fill in known unavailability in the Open Items section below | — |
| Slip allowance | 2–3 working-day-equivalents per month for sickness, work crunches, travel | — |

**Implication of the working pattern:** the focus day is for *deep* work — model bring-ups, schema design, complex coding. Evenings are for *shallow* work — annotation, reading, writeup drafting, weekly review. Schedule accordingly.

## Critical-path call-out

> **✅ DGX Spark ordered (week of 2026-05-18), ETA ~Jun 15.** The single highest-leverage week-1 action is done — and it's the one thing that _didn't_ slip. The remaining critical-path risk is now the **ETA itself**: every week the Spark is late beyond ~Jun 15 pushes Phase 3 (and everything downstream) back by the same amount. **Chase the vendor if there's no shipping update by week 3 (week of 2026-06-08).**

The plan deliberately parallelizes **Spark-independent** work into Sprint 1 so the first month is productive regardless: gold-set curation (Phase 2 start), Mac-mini-only substrate work (Phase 1 partial), and memory-adapter design (Phase 5 partial). When the Spark arrives, we slot a bring-up sub-phase ("Phase 0.5") and pivot into the Spark-dependent substrate work.

## Sprint plan (24 weeks)

Dates are **targets**, not deadlines. Slippage is expected; the slip rules below explain how we respond.

| Sprint | Calendar window | Phases active | Headline outputs |
|---|---|---|---|
| **S0 — Pre-flight** | Thu 2026-05-14 → Fri 2026-05-15 | Setup | ✅ Spark ordered. ⏭ Postgres install + first writeup draft slipped → folded into S1 wk1 |
| **S1 — Foundation, no Spark needed** | Mon 2026-05-25 → Sun 2026-06-14 (3 wk) | Phase 2 start · Phase 1 partial · Phase 5 partial | Inference-contract spec drafted; Mac-mini OpenAI-compatible endpoint live (small model); curation workflow stood up; first ~50 gold-set examples annotated; memory adapter interface designed |
| **S2 — Spark bring-up & substrate finalize** | Mon 2026-06-15 → Sun 2026-07-05 (3 wk) | Phase 0.5 · Phase 1 finalize · Phase 2 ongoing | Spark up (arrives ~Jun 15, at sprint start); blessed sovereign runtime on Spark; per-target containers; cost-discipline scaffold; gold-set v0.1 hits ~150 examples |
| **S3 — Sovereign judge stack** | Mon 2026-07-06 → Sun 2026-07-26 (3 wk) | Phase 3 · Phase 2 finalize (v0.1 release) | Specialist + generalist judges deployed on Spark; human-calibration set (100–200) built; κ ≥ 0.8 gates passed; bias stress tests run. **Phase 2 v0.1 released and frozen.** |
| **S4a — Lane depth: SEA + Japanese** | Mon 2026-07-27 → Sun 2026-08-23 (4 wk) | Phase 4 (SEA, JP) · Phase 5 starts | SEA lane deepened (SEA-LION v4 on SEA-HELM); Japanese lane deepened (Swallow + llm-jp-eval + JFinQA); memory adapter implementation begins |
| **S4b — Lane depth: OCR/VLM + Finance + Memory bake-off** | Mon 2026-08-24 → Sun 2026-09-20 (4 wk) | Phase 4 (OCR, Finance) · Phase 5 finalize | OCR/VLM lane deepened; Finance lane deepened; memory A-vs-C bake-off complete on JFinQA-with-contradiction |
| **S5 — Eval Lab v1** | Mon 2026-09-21 → Sun 2026-10-11 (3 wk) | Phase 6 | One-hour onboarding test passes; public leaderboard live; internal dashboards live; regression alerts wired |
| **S6 — Flagship application** | Mon 2026-10-12 → Sun 2026-11-01 (3 wk) | Phase 7 | Multilingual document analyst MVP → grounding → application gold set |
| **S7 — Sovereign-vs-Tier-2 cost benchmark** | Mon 2026-11-02 → Sun 2026-11-08 (1 wk) | Phase 8 | Cost report + headline numbers writeup |
| **S8+ — Stretch & beyond** | Mon 2026-11-09 → open | Phase 9 | Educational tutor and further apps as they justify themselves |

End of Phase 8 target: **~first week of November 2026** (≈ 24 weeks from the 2026-05-25 start). Phase 9+ continues indefinitely.

## Sprint 1 — week-by-week detail

The first 3 weeks are detailed because that's when the rhythm gets set. Later sprints are detailed at the start of each sprint, not now (over-planning past the next horizon is wasted work).

### Week 1 · Mon 2026-05-25 → Sun 2026-05-31

**Theme:** Lay the substrate foundation on the Mac mini. Begin gold-set workflow design. (Spark order already shipped — see S0.)

| Day | Slot | Tasks |
|---|---|---|
| Mon 25 | Evening (~2 hr) | ✅ **Spark already ordered** on the original schedule (week of 2026-05-18), ETA ~Jun 15. This slot instead: stand up local Postgres on the Mac mini (Homebrew + `pgvector` installed but not exercised). Postgres database `ai_experiments` created. *(pulled forward from the slipped S0)* |
| Tue 26 | Evening (~2 hr) | Read the inference-contract spec outline from earlier discussion. Draft section headings of `docs/superpowers/specs/2026-05-14-evaluation-system-design.md`. |
| Wed 27 | Evening (~2 hr) | Read NIM-on-Spark playbook + TensorRT-LLM quickstart + vLLM-Metal docs. Document the runtime trade-offs in `docs/notes/runtime-choices.md`. |
| Thu 28 | Evening (~2 hr) | Confirm the Spark shipping update has landed; if not, chase the vendor. Buffer for any of the above that ran long. |
| **Fri 29** | **Focus day (~7 hr)** | **Inference-contract spec draft v0.1.** Define the endpoint shape (likely OpenAI-compatible `/v1/chat/completions` + `/v1/embeddings`), required vs optional fields, sampling params, model-id resolution, error semantics. Commit. |
| Sat 30 | Optional (~2 hr) | Run a small model on Mac via `mlx-lm.server` or `ollama serve` behind the inference contract. Hit it with `curl`. Validate the contract design end-to-end on toy traffic. |
| Sun 31 | Review (~30 min) | **Weekly review.** Update `ROADMAP.md` statuses (Phase 1 partial → `in progress`); write the week's journal entry in `docs/notes/journal/2026-05-31.md`. |

### Week 2 · Mon 2026-06-01 → Sun 2026-06-07

**Theme:** Run-storage schema. First gold-set lane (general reasoning) starts. Inference contract validated.

| Day | Slot | Tasks |
|---|---|---|
| Mon 01 | Evening | Draft the `run` table schema in `docs/superpowers/specs/2026-05-14-evaluation-system-design.md`: `(model_manifest, gold_set_version, judge_config, results, traces, cost, started_at, finished_at)`. Migration file scaffolded. |
| Tue 02 | Evening | First experiment folder: `experiments/0001-inference-contract-validation/`. README with Hypothesis/Setup/Method drafted. Wire a tiny eval harness that hits the Mac endpoint and writes to the `run` table. |
| Wed 03 | Evening | Gold-set workflow: write the contributor doc in `experiments/0005-eval-curation-workflow/README.md` (seed → expand → filter → annotate → review → release). Decide the annotation-tool bake-off candidates: argilla and label-studio. |
| Thu 04 | Evening | Read argilla and label-studio docs. Pick which one to try first (recommend argilla for SQL-native + Python-first). |
| **Fri 05** | **Focus day** | Stand up argilla locally on Mac mini. Annotate ~15 general-reasoning examples to test the workflow end-to-end. Document friction. |
| Sat 06 | Optional | Continue annotating; aim for ~30 general-reasoning examples by Sunday. |
| Sun 07 | Review | Weekly review + monthly retrospective (May 25 – Jun 7). First social-post draft for `docs/social/phase-1-inference-contract.md` (the "why I'm starting with sovereignty" teaser). |

### Week 3 · Mon 2026-06-08 → Sun 2026-06-14

**Theme:** Memory-adapter interface design. Continue gold-set annotation. Spark ETA confirmation.

| Day | Slot | Tasks |
|---|---|---|
| Mon 08 | Evening | **Confirm Spark ETA.** If shipping update hasn't come, chase the vendor. Update PLAN.md with the latest expected date. |
| Tue 09 | Evening | Design the `shared/memory/` adapter interface: write/recall_semantic/recall_entity/traverse/snapshot/restore. Draft a tiny test harness that exercises the interface with an in-memory mock backend. Commit. |
| Wed 10 | Evening | Continue gold-set annotation: aim for SEA-language lane start (~10–15 examples). |
| Thu 11 | Evening | Continue gold-set annotation: Japanese-lane start (~10 examples) — quick sanity check on rendering and font support in argilla. |
| **Fri 12** | **Focus day** | Move the inference contract from spec to code: a minimal `shared/inference/` Python adapter that talks to any OpenAI-compatible endpoint. Update `experiments/0001-...` to use it. |
| Sat 13 | Optional | Begin writing the first long-form draft in `docs/writeups/phase-1-sovereign-inference-substrate.md` (will continue through S2). |
| Sun 14 | Review | Weekly review. Plan Sprint 2 — Spark should be arriving ~now (Jun 15), so S2 bring-up starts Monday. |

End of Sprint 1 targets: inference-contract spec + code committed; Mac-mini eval loop runs end-to-end on a toy lane; gold-set ≥ 50–80 examples; memory adapter interface designed; first writeup draft underway; Spark in transit with a hard ETA.

## Rituals

- **Weekly review** — Sunday evening, 30 min. Update phase statuses in `ROADMAP.md` + `EXPERIMENTS.md`; write a 3–5 line journal entry in `docs/notes/journal/YYYY-MM-DD.md`; if anything has slipped > 50%, raise it in the entry.
- **Monthly retrospective** — first weekend of each month, ~1 hr. Looks back at the month, surfaces what's actually going well or badly, posts a retrospective short-form thread (drafted in `docs/social/`).
- **Phase completion gate** — a phase isn't "done" until its writeup is **published** (URL recorded in the draft's front-matter) **and** the short-form bundle has gone out. No starting the next phase's substantive work until the current phase's docs ship.
- **Daily journal-of-one-line** — optional but recommended. At end of each work slot, jot one line in the current weekly journal entry. Costs ~30 sec; saves enormous time when writing the retrospective and the long-form post.

## Slip rules

- **Phase ≥ 50% over time budget** → pause work, write a one-page "what I missed" note in `docs/notes/`, decide whether to descope or re-estimate. Don't push on without doing this.
- **Spark ETA slips > 2 weeks beyond target (Jun 15 → past Jun 29)** → pivot harder into Phase 5 (memory) earlier; push Phase 3 (judges that need Spark) right. Reassess the Phase 8 target.
- **3 consecutive weeks below 10 hr** → recalibrate the whole plan downwards. Comprehensiveness over speed; better to acknowledge the lower cadence than to silently slip every phase by 30%.
- **Burnout signal** (working > 16 hr/week for 2 weeks straight) → enforce a fallow week. The plan is multi-month; sustaining the cadence beats sprinting and crashing.

## Open items (decide soon)

- [x] **Spark order placed (week of 2026-05-18)** — on the original schedule; ETA ~Jun 15. Chase the vendor if no shipping update by week 3 (week of 2026-06-08).
- [ ] **Annotation tool** — argilla vs label-studio decided by end of week 2.
- [ ] **Singapore public holidays / known blocked weeks** in the next 6 months — please add to the table below as you spot them so the calendar can absorb them upfront. Vesak Day, Hari Raya Haji, National Day (Aug 9), Deepavali are the obvious ones for 2026.
- [x] **Publication pattern decided (2026-05-14):** **Substack canonical + HubSpot (SG Code Campus) excerpt-and-link.** Substack subscribers receive the full article (preserves the newsletter / Notes / recommendations mechanic); HubSpot publishes a ~3-paragraph excerpt + "Read the full deep dive on `<Substack>`" pointing back, with a short bio tying the author to SG Code Campus. The repo `docs/writeups/` stays the markdown source of truth; the Substack URL is recorded in each draft's front-matter once published.
- [x] **Substack name decided (2026-05-15): "Workings"** — from the educator's "show your workings" phrase. Broad, durable, single word, distinctive.
- [ ] **Reserve `workings.substack.com` this week** before publishing anything. Fallback URL slugs if taken (the *publication name* stays "Workings" regardless): `theworkings`, `workings-notes`, `workings-by-jonathan`, `workingsweekly`. Substack lets you change the URL slug later if you take a custom domain (e.g., `workings.jonathandoh.com`) on the paid tier.
- [x] **Substack subtitle decided (2026-05-15):** *"Working through AI, education, and the craft of figuring things out — in public."* About page + welcome-post drafts ready at [`docs/social/substack-setup.md`](docs/social/substack-setup.md) — paste verbatim when reserving.
- [ ] **Dashboard stack** for Phase 6 — Grafana on Postgres vs custom Next.js. Decided no later than Sprint 4 (we want to start instrumenting toward it earlier).
- [ ] **Cloud burst provider** — which of GCE A3 / AWS P5 / Runpod / Lambda is the default on-demand target? Decided by Sprint 3 (when first heavy-compute eval is queued).

### Known unavailability

| Window | Reason | Adjustment |
|---|---|---|
| _add as you spot them_ | — | — |

## What's not in this plan (but should be soon)

- **A separate eval-system spec** at `docs/superpowers/specs/2026-05-14-evaluation-system-design.md` covering the four hard-to-reverse decisions (inference contract, run-storage schema, gold-set taxonomy, judge protocol). The spec is the *substance* behind the Sprint 1 work; this PLAN.md sequences it. Drafting the spec is the first deep-work item of week 1.
- **A separate budget doc** if cloud spend turns out to be non-trivial in Phase 4 onwards. Probably not needed before Sprint 3.
