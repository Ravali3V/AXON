# AXON — Amazon Excellence Operations Network

End-to-end Amazon seller growth, automation, and intelligence platform.

## Structure

```
apps/AXON/
├── frontend/       # React (Vite) — seller + admin UI
├── backend/        # NestJS API (Custom JWT, Audits module, SSE, Cloud Tasks)
├── ai-proxy/       # Python FastAPI — centralized Claude proxy with cost tracking
├── worker/         # Python Playwright audit worker (scrape + score + enrich + render PDF)
├── shared/         # Shared TypeScript types across frontend + backend
├── infra/          # Docker, Terraform, DB migrations, Cloud Build configs
├── docs/           # DESIGN_DECISIONS, FEATURES, API_DOCS, DATABASE, USER_GUIDE, plans/
├── VERSION
├── CLAUDE.md       # Per-project standing instructions for Claude Code
└── README.md
```

## Tech Stack (locked)

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite, deployed to Cloud Run |
| Backend | NestJS 10 on Node 20, deployed to Cloud Run |
| AI Proxy | Python FastAPI, deployed to Cloud Run |
| Worker | Python 3.11 + Playwright + residential proxies, deployed to Cloud Run |
| Database | PostgreSQL 15 on GCP Cloud SQL (local: Docker) |
| Auth | Custom JWT (bcrypt), built into NestJS |
| Storage | GCS (`axon-reports` bucket) |
| Queue | Cloud Tasks (local: in-process fallback) |
| LLM | Claude via FastAPI proxy — Sonnet + Haiku |

**Non-negotiable constraints:**
1. Every Claude call routes through the AI Proxy (`apps/AXON/ai-proxy/`). Zero direct SDK calls from other services.
2. Multi-tenant isolation from day 1: Postgres RLS + API-level `org_id` guards + AI context scoping.
3. All AI suggestions require human approval — no auto-apply.
4. Amazon guidelines are a hard constraint above the learning system.

## Getting Started (local dev)

Prerequisites: Node 20+, pnpm 9+, Python 3.11+, Docker Desktop.

```bash
# 1. Install JS dependencies
pnpm install

# 2. Start local Postgres
pnpm run db:up

# 3. Run DB migrations + seed default org
pnpm run db:migrate
pnpm run db:seed

# 4. Start each service in its own terminal:
#    - Frontend (Vite dev server)
#    - Backend (NestJS)
#    - AI Proxy (uvicorn)
#    - Worker (python -m src.pipeline.orchestrator)
```

See per-service README for details.

## Active Phase

Phase 1 — Foundation. Building Brand Audit Tier 1 (v1).
See [docs/plans/tier1-brand-audit-v1.md](docs/plans/tier1-brand-audit-v1.md).
