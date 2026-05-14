# Writeups

Long-form technical articles, one per phase (and sometimes one per major experiment within a phase).

**Workflow:**

1. Draft as `phase-N-<slug>.md` in this folder while the phase is in progress. Use the front-matter template below.
2. Publish to the chosen platform (own blog / Substack / Medium / dev.to — see `ROADMAP.md` open questions).
3. Record the published URL in the draft's front-matter; keep the draft in the repo as the canonical source.
4. Documentation completion is part of "phase done" per the Operating Model in `ROADMAP.md`.

**Front-matter template:**

```yaml
---
phase: 1
slug: sovereign-inference-substrate
status: draft        # draft · ready-to-publish · published
published_url:       # filled in once live
published_date:      # YYYY-MM-DD when live
title: "Building a sovereign LLM inference substrate"
tags: [sovereignty, llm, dgx-spark, mac-mini, eval]
---
```

**Length / shape guideline:** ~2 000–4 000 words. Code snippets and charts where they earn their space. Embed the chart source so figures can be regenerated; link back to the relevant experiment folders in `experiments/` so readers can dig in.
