# PLAN — Brand Audit Tier 1 (v1)

**Status:** READY FOR LOCAL DRY-RUN
**Owner:** AXON founding team (Claude Code-driven)
**Created:** 2026-04-21
**Target:** viable by end of June 2026

Authoritative plan at `C:\Users\user\.claude\plans\the-summary-is-almost-optimized-charm.md`. This file is the per-project mirror.

---

## Pipeline Position

Per `D:\Projects\BUILD.md` — New App Pipeline (AXON is a new application).

- [x] Stage 0 — Exploration Agent: Briefing delivered + user-approved as plan file.
- [x] Stage 1 — PM Agent: Scope and project plan finalized (in the approved plan).
- [x] Stage 2 — Architecture Agent: DB schema approved in plan; implemented in T-03.
- [~] Stage 3 — Infrastructure Agent: local Docker Postgres stack live; GCP provisioning script ready (T-02), user to run from Cloud Shell.
- [x] Stage 4 — Testing Agent (Design): unit tests for parsers, rubric, pricing, + tenant isolation integration test.
- [x] Stage 5 — Programming Agent (New App): all 14 build tasks (T-01, T-03–T-15) complete.
- [ ] Stage 6 — Review Agent: pending (kicked off after local dry-run confirms a real audit runs end-to-end).
- [ ] Stage 7 — Testing Agent (Verification): run full test suite against local stack.
- [ ] Stage 8 — Deployment Agent: run provisioning script; deploy each service to Cloud Run; final handover.

---

## Task Progress

| ID | Task | Status |
|---|---|---|
| T-01 | Monorepo skeleton | DONE |
| T-02 | GCP Cloud SQL + GCS + Secret Manager + Cloud Tasks | READY (Cloud Shell script `infra/cloudbuild/provision.sh`) |
| T-03 | DB migrations + RLS + default-org seed | DONE |
| T-04 | AI Proxy service (FastAPI) + cost tracking | DONE |
| T-05 | NestJS API Audits module + Cloud Tasks enqueue + SSE | DONE |
| T-06 | Worker: brand resolution + ASIN discovery + proxy harness + selector registry | DONE |
| T-07 | Worker: per-ASIN PDP scrape | DONE |
| T-08 | Worker: Brand Store + Brand Story + video + reviews | DONE |
| T-09 | Scoring engine (100-pt) | DONE |
| T-10 | LLM enrichment via AI Proxy | DONE |
| T-11 | PDF generation (Puppeteer sidecar + GCS upload) | DONE |
| T-12 | React Input + Progress screens | DONE |
| T-13 | React Report Viewer + Methodology | DONE |
| T-14 | React Override + Re-score | DONE |
| T-15 | End-to-end hardening + cost dashboard + prospect dry-run docs | DONE (dry-run pending user) |

---

## Next Actions

1. Follow `HOWTO_LOCAL.md` — bring the stack up locally and run an audit against a known brand.
2. When satisfied: open GCP Cloud Shell in the browser and run `bash infra/cloudbuild/provision.sh` (project is already `axon-494010`).
3. Sign up for a residential proxy provider (IPRoyal recommended for pay-as-you-go), drop creds into `.env` (local) and Secret Manager (prod).
4. Get an Anthropic API key and drop into `.env` / Secret Manager. Without it, the AI Proxy runs in stub mode and returns canned narrative text (the pipeline still works, the PDFs just have placeholder prose).
5. Run through your current prospect brand list end-to-end.
6. Report findings; we'll iterate on the rubric, selectors, and prompts.

---

## Files of Note

- [HOWTO_LOCAL.md](../../HOWTO_LOCAL.md) — local run instructions
- [infra/cloudbuild/provision.sh](../../infra/cloudbuild/provision.sh) — T-02 Cloud Shell script
- [worker/src/scoring/rubric.py](../../worker/src/scoring/rubric.py) — 100-point rubric implementation
- [worker/src/scrape/selectors.py](../../worker/src/scrape/selectors.py) — centralized Amazon selector registry
- [worker/src/pipeline/orchestrator.py](../../worker/src/pipeline/orchestrator.py) — master pipeline
- [frontend/src/pages/Methodology.tsx](../../frontend/src/pages/Methodology.tsx) — rubric viewer + "suggest a change"
