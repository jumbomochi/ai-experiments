# Substack setup — "Workings"

Paste-ready content for reserving and configuring the Substack publication. Used once on initial reservation; this file then becomes a reference for how the publication is configured.

## Publication settings

- **Name:** Workings
- **URL (try in order):** `workings.substack.com` → `theworkings` → `workings-notes` → `workings-by-jonathan` → `workingsweekly`
- **Subtitle:** Working through AI, education, and the craft of figuring things out — in public.
- **Author display name:** Jonathan Doh
- **Logo:** TBD (placeholder for now — text-only Substack header is fine for v1)
- **Custom domain (paid tier, optional later):** e.g. `workings.jonathandoh.com`

## About page

Paste verbatim into Substack's About section.

---

Hi — I'm Jonathan. I teach at SG Code Campus in Singapore and spend the rest of my time running an open AI experiments lab.

"Workings" comes from "show your workings" — the phrase teachers use to make students reveal their reasoning, not just their answers. This newsletter is mine: a long-form notebook of what I'm building, what I'm teaching, and what I'm still figuring out, written down so it doesn't stay in my head.

The current focus is a sovereign LLM evaluation lab — running open-weight models on my own hardware, building gold-set benchmarks privately, and trying to make local-first AI development a serious alternative to renting cognition from proprietary APIs. The repo is at [github.com/jumbomochi/ai-experiments](https://github.com/jumbomochi/ai-experiments).

Expect:

- Long-form deep dives into the experiments — sovereignty, evaluation, agent memory, local-first deployment — with code, charts, and honest results, including the ones that didn't work.
- Notes from teaching ML and software to the next cohort of builders in Singapore.
- Occasional detours into SEA + Singapore AI policy, Japanese tooling, and whatever else catches my attention long enough to write a few thousand words about.

No paid tier yet. No "AI hot takes." Slow, comprehensive, evidence-first — the kind of writing I wish more practitioners in this field did.

— Jonathan

---

## Welcome post (pinned)

The first post — pinned to the top, sent as a one-time welcome email to new subscribers via Substack's welcome-email setting.

**Title:** Welcome to Workings
**Subtitle (optional):** What this newsletter is, and what's coming.

---

Hi — if you're reading this, you've subscribed to a newsletter that doesn't have many posts yet. The first essays are queued; they'll arrive as I finish them.

Here's the deal.

I'm running a multi-phase AI experiments project at [github.com/jumbomochi/ai-experiments](https://github.com/jumbomochi/ai-experiments) — a sovereign LLM evaluation lab, built on my own hardware, with privately-curated gold sets and locally-deployed judge models. It's an extended bet that AI builders are better served by sovereign tools than by paying for SOTA proprietary APIs forever.

Each phase of that project ends in a long-form writeup here. Between phases you'll get shorter retrospectives, reading notes, and detours into teaching, Singapore's AI scene, and whatever else takes my attention long enough.

No paid tier. No clickbait. No marketing copy. Just slow, comprehensive, evidence-first notes — written because I've already done the work and want to share what I learned.

The first long-form post lands when Phase 1 (the sovereign inference substrate) wraps. Until then, you'll get the occasional short note while I build.

See you in the next post.

— Jonathan

---

## Sections (Substack categories)

Substack lets posts be organized into sections. Suggested set — only create a section when you have ≥ 2 posts ready for it; until then, single feed.

- **The lab** — long-form per-phase writeups from `ai-experiments` (Phases 1–8 of the roadmap).
- **Notes** — shorter retrospectives, monthly recaps, reading notes.
- **Teaching** — observations from teaching ML / software at SG Code Campus.
- **Detours** — everything else (SEA AI policy, Japanese tooling, occasional opinion).

## Cross-post checklist (per published long-form writeup)

When publishing each phase's long-form writeup:

1. Publish canonical on Substack (full article).
2. Copy the Substack URL into the draft's `substack_url` front-matter field in `docs/writeups/`.
3. Cross-post a ~3-paragraph excerpt to the SG Code Campus HubSpot site with a "Read the full deep dive on [Workings](<substack_url>)" link and a short author bio.
4. Copy the HubSpot URL into the draft's `hubspot_url` front-matter field.
5. Set the HubSpot post's `rel="canonical"` to the Substack URL (SEO hygiene — Substack wins the full piece; HubSpot gets brand association).
6. Short-form bundle posts (LinkedIn / X / Bluesky / Mastodon, and Substack Notes) all link to the Substack canonical, not the HubSpot excerpt.

## Once reserved

When the Substack URL is reserved, update:

- `PLAN.md` — Open Items: tick the reservation checkbox; record the actual URL.
- `ROADMAP.md` — no edit needed (publication pattern already locked).
- This file's *Publication settings* block (replace "try in order" with the actual URL).
