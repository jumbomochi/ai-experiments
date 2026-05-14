# Writeups

Long-form technical articles, one per phase (and sometimes one per major experiment within a phase).

**Workflow:**

1. Draft as `phase-N-<slug>.md` in this folder while the phase is in progress. Use the front-matter template below.
2. Publish **canonical on Substack** (full article — subscribers get it by email, the article enters the Substack network).
3. Publish an **excerpt + link** on the SG Code Campus HubSpot site (~3 paragraphs + "Read the full deep dive on `<Substack>`" + bio tying to the company).
4. Record both URLs in the draft's front-matter. The markdown draft in this folder remains the long-term source of truth.
5. Documentation completion is part of "phase done" per the Operating Model in `ROADMAP.md`.

**Front-matter template:**

```yaml
---
phase: 1
slug: sovereign-inference-substrate
status: draft               # draft · ready-to-publish · published
substack_url:               # filled in once published
hubspot_url:                # filled in once cross-posted
published_date:             # YYYY-MM-DD when canonical goes live
title: "Building a sovereign LLM inference substrate"
tags: [sovereignty, llm, dgx-spark, mac-mini, eval]
---
```

**Length / shape guideline:** ~2 000–4 000 words. Code snippets and charts where they earn their space. Embed the chart source so figures can be regenerated; link back to the relevant experiment folders in `experiments/` so readers can dig in.
