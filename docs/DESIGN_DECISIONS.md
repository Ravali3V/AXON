# AXON — Design Decisions

This document records product and technical decisions with their rationale.
Update it whenever a decision is made, reversed, or changed. The goal is to
prevent re-debating settled questions and to give future sessions full context.

---

## How to Use

Each decision follows this format:
- **Decision:** What was decided
- **Date:** When it was decided
- **Context:** Why it came up
- **Rationale:** Why this option was chosen over alternatives
- **Alternatives considered:** What else was evaluated

---

## Decisions

### D1: Tech stack — self-owned, on Google Cloud, no third-party BaaS

**Decision:** Frontend React (Vite) + Backend NestJS + AI Proxy Python FastAPI + Worker Python Playwright, all on GCP Cloud Run. PostgreSQL on Cloud SQL. Custom JWT auth (bcrypt). GCS for file storage.
**Date:** 2026-04-21
**Context:** Founding-team onboarding decision — what to build AXON on.
**Rationale:** Two-person part-time team + Claude Code for dev + viable by end of June 2026. Self-owned stack avoids vendor lock-in, keeps costs predictable, and concentrates all ops on one cloud. Custom JWT is simple enough for Claude Code to maintain and avoids any third-party auth provider.
**Alternatives considered:** Angular (per docx §7.2) — rejected for slower React-vs-Angular Claude Code velocity. Vercel for frontend — rejected for "everything on GCP" consistency. Firebase Auth / Supabase / Auth0 — rejected for self-owned principle. Keepa / Helium 10 / Rainforest API for Amazon data — rejected for the same reason; Playwright scraper is self-built.

### D2: Build Brand Audit Tier 1 as the first AXON feature

**Decision:** Phase 1's flagship deliverable — Tier 1 Brand Audit — is the first thing built. Every other AXON feature waits.
**Date:** 2026-04-21
**Context:** Team needs to deliver audits to a few prospective sellers immediately (pre-sales, time-critical). No AXON code exists yet.
**Rationale:** Tier 1 is the smallest slice that delivers standalone value AND forces the foundational plumbing (scraper, AI proxy, PDF, Postgres, Cloud Run) into existence. Every later feature reuses that substrate.
**Alternatives considered:** Start with Seller Dashboard (docx §8.1) — rejected; can't be tested without sellers onboarded. Start with Admin Dashboard — rejected for the same reason.

### D3: Extended 100-point rubric (not the docx's 60-point Tier 1)

**Decision:** Tier 1 scoring uses a 100-point extended rubric: Listing Quality 25, Review Health 15, Buy Box & Pricing 10, BSR & Sales Velocity 10, Catalog & Brand Presence 10, Video Presence 10, Brand Story 10, Brand Store Quality 10.
**Date:** 2026-04-21
**Context:** User directed that the docx 60-pt rubric is "reference only" and explicitly asked for additional categories (Video, Brand Story, Brand Store) to make the report stronger. Also asked for 100 points total.
**Rationale:** Scoring out of 100 aligns with intuitive letter grades (A/B/C/D/F on 90/80/70/60 thresholds). New sections reflect real 2026 Amazon signals — video content, Brand Story module, Brand Store quality — that the docx rubric under-weights.
**Alternatives considered:** Stick with docx 60-pt + separate informational section for video/brand-story/brand-store — rejected because it hides those signals from the grade. 120-pt rubric — rejected for grade clarity.

### D4: No historical data in v1 (no Keepa, no self-scraped backfill)

**Decision:** Tier 1 v1 captures a single point-in-time snapshot. Trend-based criteria (BSR trend, pricing consistency) degrade to `warning` status ("insufficient data — requires 30+ days of tracking") and do not penalize the score.
**Date:** 2026-04-21
**Context:** User: "For current scenario… we need the data right now… if we could get any without any third party we would be bringing that data then after we would decide on third party apps or self-built."
**Rationale:** Ship to real prospects this week rather than wait 90 days for self-scraped history. Decision on Keepa vs self-built historical scraper deferred until after v1 validates with real users.
**Alternatives considered:** Add Keepa ($20/mo) for history — deferred, not rejected. Self-scrape daily from day 1 — deferred; infra is too young for a daily cron.

### D5: No login in v1 — schema ready for Custom JWT in v1.1

**Decision:** v1 ships without authentication. All audits attribute to a seeded default organization ("AXON Internal"). Postgres RLS policies and API-level `org_id` guards are written and active from day 1 against that single org so Custom JWT can slot in without schema refactor.
**Date:** 2026-04-21
**Context:** User: "First to check the functionalities we would be doing without login but if everything is working fine we would be needing a login screen."
**Rationale:** Fastest path to validating functionality. Tenant plumbing is real (not stubbed) so v1.1 is a UI + middleware change only.
**Alternatives considered:** Ship with login immediately — rejected for speed. Ship with no tenant plumbing — rejected; would require invasive refactor when auth lands.

### D6: All ASINs, all reviews — no artificial cap (soft/hard safety guards only)

**Decision:** Tier 1 scrapes every ASIN under a brand and every review per ASIN. Soft warning at 500 ASINs / 20,000 reviews; hard ceiling 2,000 ASINs / 50,000 reviews.
**Date:** 2026-04-21
**Context:** User: "all asins and all reviews."
**Rationale:** Rubric fidelity — capping ASIN coverage distorts Catalog Depth and Variation Strategy scoring; capping reviews distorts sentiment analysis. For the expected volume (handful of prospect audits) the proxy/cost impact is modest.
**Alternatives considered:** 50 ASIN × 20 review cap (Plan agent default) — rejected by user. Hard cap only, no soft warning — rejected; large catalogs should warn operators before running.

### D7: Async UX with live Progress screen (not the docx's 2–5 minute sync promise)

**Decision:** Audit runs async. Input screen submits → Progress screen streams live stage updates over SSE → Report Viewer opens when complete. Realistic runtime: 10–30 minutes depending on brand size.
**Date:** 2026-04-21
**Context:** Docx §2.1 claims Tier 1 is "2–5 minutes, fully automated." Research + the "all ASINs, all reviews" decision make that unrealistic.
**Rationale:** Honest UX. Operators can start an audit and walk away; the Progress screen keeps the confidence that something's happening. Cloud Tasks queue makes per-task retry free.
**Alternatives considered:** Email-only ("we'll email when done") — rejected; Progress screen is more confidence-inspiring. Cap audit at <5 min — rejected via D6.

### D8: Puppeteer print-to-PDF (not React-PDF)

**Decision:** PDF is generated by headless Chromium (Puppeteer) invoked from a Node sidecar inside the worker container. Uses the exact same HTML/CSS as the in-app Report Viewer.
**Date:** 2026-04-21
**Context:** Needed a PDF engine for the audit report.
**Rationale:** Single-source-of-truth styling — what the user sees in the app is what they see in the PDF. React-PDF's layout model is too limited for data-heavy reports. wkhtmltopdf is abandoned.
**Alternatives considered:** React-PDF — rejected for layout limitations. wkhtmltopdf — rejected as unmaintained. Server-side Playwright print (already in worker) — viable; chose Puppeteer sidecar specifically so PDF rendering doesn't compete with Playwright scrape workers for the same browser pool.
