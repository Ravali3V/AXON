# AXON — Feature Registry

Tracks built, planned, and rejected features. Update when scope changes.

---

## Status Legend

- `PLANNED` — on roadmap, not yet started
- `IN_PROGRESS` — active development
- `BUILT` — shipped and in production
- `REJECTED` — considered and explicitly not doing

---

## Features

| ID | Feature | Status | Notes |
|---|---|---|---|
| F1 | Brand Audit Tier 1 — scrape + 100-pt score + PDF | IN_PROGRESS | See `docs/plans/tier1-brand-audit-v1.md`. v1 has no login. |
| F1.a | Input screen (brand-name + Start) | PLANNED | T-12 |
| F1.b | Progress screen (SSE stage stream) | PLANNED | T-12 |
| F1.c | Report Viewer + PDF download | PLANNED | T-13 |
| F1.d | Methodology explainer + "suggest a rubric change" | PLANNED | T-13 |
| F1.e | Manual Override + scoring-only Re-score | PLANNED | T-14 |
| F1.f | Playwright scraper (brand + ASINs + reviews + Brand Store + Brand Story) | PLANNED | T-06/T-07/T-08 |
| F1.g | 100-pt scoring engine with data-availability statuses | PLANNED | T-09 |
| F1.h | LLM enrichment via AI Proxy (narrative, S/W, recs, Quick Wins, review sentiment) | PLANNED | T-10 |
| F1.i | PDF renderer (Puppeteer sidecar) + GCS upload | PLANNED | T-11 |
| F2 | Login / signup (Custom JWT) | PLANNED | v1.1, schema already ready. |
| F3 | Historical BSR / pricing tracking | PLANNED | Deferred until after v1 validation. Decision on Keepa vs self-built pending. |
| F4 | Brand Audit Tier 2 (SP-API + account-level data) | PLANNED | Phase 2 per docx. Requires seller OAuth. |
| F5 | Seller Dashboard (sales, ads, profitability) | PLANNED | Phase 1 per docx. Post-Tier-1. |
| F6 | Admin Dashboard (multi-client overview) | PLANNED | Phase 1 per docx. |
| F7 | Keepa integration | REJECTED (deferred) | User preference for no-third-party v1. May re-evaluate after v1. |
| F8 | Firebase Auth | REJECTED | Custom JWT chosen instead — "everything self-owned." |
