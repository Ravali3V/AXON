# AXON — Local Dev + Test Guide

Exactly what to run to bring the whole stack up on your machine and audit a real brand end-to-end.

## Prerequisites (one-time install)

| Tool | Version | How to check |
|---|---|---|
| Docker Desktop | latest | `docker --version` |
| Node | 20+ | `node --version` |
| pnpm | 9+ | `pnpm --version` (install: `npm i -g pnpm@9`) |
| Python | 3.11+ | `python --version` |

## 1. Copy the env template

```bash
cd d:/Projects/apps/AXON
cp .env.example .env
```

Open `.env` and fill in:
- `ANTHROPIC_API_KEY` — leave as-is if you don't have one yet; the AI Proxy runs in stub mode and the pipeline still works end-to-end (you just get canned narrative text instead of real Claude output).
- `PROXY_ENDPOINT`, `PROXY_USERNAME`, `PROXY_PASSWORD` — leave blank for now; Amazon will serve CAPTCHAs after ~10 pages but you can still see the pipeline run.

## 2. Start Postgres

```bash
pnpm run db:up
```

Verify: `docker ps` should show `axon-postgres-dev` as `(healthy)`.

## 3. Install dependencies

```bash
# JS monorepo (frontend + backend + shared)
pnpm install

# Python — AI Proxy
cd ai-proxy
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
cd ..

# Python — Worker (includes Playwright; first run downloads ~200MB of Chromium)
cd worker
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m playwright install chromium
cd ..

# Node sidecar for PDF generation
cd worker/pdf_sidecar
npm install
cd ../..
```

## 4. Run migrations and seed

```bash
pnpm --filter @axon/backend run migration:run
pnpm --filter @axon/backend run seed
```

Expected output from seed: `[seed] default org: 00000000-0000-0000-0000-000000000001 "AXON Internal"`.

## 5. Start the four services

Open four terminals. Each command is run from `d:/Projects/apps/AXON`.

**Terminal A — Backend (port 4000):**
```bash
pnpm --filter @axon/backend run start:dev
```
Wait for: `[axon-backend] listening on :4000`.

**Terminal B — AI Proxy (port 8080):**
```bash
cd ai-proxy
.venv/Scripts/python -m uvicorn src.main:app --port 8080 --reload
```

**Terminal C — Worker (port 9090):**
```bash
cd worker
.venv/Scripts/python -m uvicorn src.main:app --port 9090 --reload
```

**Terminal D — Frontend (port 5173):**
```bash
pnpm --filter @axon/frontend dev
```

## 6. Run an audit

Open <http://localhost:5173> in a browser.

1. Enter a brand name (e.g. `Anker`).
2. Click Start audit.
3. Watch the Progress screen — stages tick through: Resolving → Discovering ASINs → Scraping PDPs → Brand Store → Reviews → Scoring → Enriching → Rendering PDF.
4. When complete, you're redirected to the Report. Click Download PDF.
5. Click Methodology in the nav to see the full 100-point rubric.
6. From the Report, click "Manual Override & Re-score" to correct any scraped value and re-run scoring.

## 7. Expected behaviour without a residential proxy

- First ~10 pages may scrape fine.
- After that Amazon throws robot-check pages.
- The pipeline detects it, retries 3× on fresh browser contexts, then degrades affected criteria to `warning` status — the audit still completes, just with more gaps.

This is expected. Add real proxy credentials to `.env` (`PROXY_ENDPOINT`, `PROXY_USERNAME`, `PROXY_PASSWORD`) when you sign up with IPRoyal / Oxylabs / Smartproxy — the code already uses them if present.

## 8. Spot-check the database

```bash
docker exec -it axon-postgres-dev psql -U axon -d axon -c \
  "SELECT id, brand_name, status, grade, score_total, score_possible, version
   FROM audits ORDER BY started_at DESC LIMIT 5;"

# Event log for a specific audit
docker exec -it axon-postgres-dev psql -U axon -d axon -c \
  "SELECT ts, stage, level, left(message, 80) AS msg
   FROM audit_events WHERE audit_id = 'YOUR-AUDIT-UUID'
   ORDER BY ts DESC LIMIT 30;"

# AI proxy cost log
docker exec -it axon-postgres-dev psql -U axon -d axon -c \
  "SELECT provider, model, purpose, cost_usd, latency_ms, created_at
   FROM ai_usage_logs ORDER BY created_at DESC LIMIT 10;"
```

## 9. Cost summary endpoint

```bash
curl http://localhost:4000/api/cost-summary?days=7
```

## 10. Tear down

```bash
pnpm run db:down      # stops Docker Postgres (data persists in a volume)
```

To wipe data entirely: `docker volume rm axon_axon-postgres-data`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `FATAL: role "axon" does not exist` | Postgres not migrated | `pnpm --filter @axon/backend run migration:run` |
| Backend 500 on `POST /api/audits` | Worker isn't running | Start worker (Terminal C) |
| Progress stuck on `queued` | `WORKER_URL` wrong or worker port blocked | Check `.env`; default is `http://localhost:9090` |
| PDF download fails with "Not yet generated" | Audit didn't reach `complete` status | Check `audit_events` for the failure |
| Worker CAPTCHA every request | No proxy, running headless=true | Add residential proxy creds OR set `PLAYWRIGHT_HEADLESS=false` to debug |
| "PDF sidecar not found" | Forgot `npm install` in `worker/pdf_sidecar` | Run it |
| LLM enrichment skipped with stub text | No Anthropic key | Expected — set `ANTHROPIC_API_KEY` in `.env` and restart AI Proxy |
