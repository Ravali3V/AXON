# AXON — Database

PostgreSQL 15. Local: Docker Compose (`infra/docker/docker-compose.dev.yml`). Prod: Cloud SQL.

Migrations live in `infra/migrations/` and run via TypeORM (`pnpm run db:migrate`).

---

## Multi-Tenancy

Every tenant-scoped table has:
- `org_id uuid NOT NULL` column, indexed.
- An RLS policy: `USING (org_id = current_setting('app.current_org', true)::uuid)`.
- NestJS sets `SET LOCAL app.current_org = '<uuid>'` at the start of each request transaction.

In v1 there is a single seeded organization (see `DEFAULT_ORG_ID` in `.env.example`). The plumbing is real so v1.1 auth drops in without refactor.

---

## Tables (created in T-03)

The initial schema migration is at [backend/src/database/migrations/1713700000000-initial-schema.ts](../backend/src/database/migrations/1713700000000-initial-schema.ts).

Run locally:
```bash
pnpm run db:up         # start Docker Postgres
pnpm run db:migrate    # apply the initial migration
pnpm run db:seed       # insert the default "AXON Internal" org
```

TypeORM entities are at [backend/src/database/entities/](../backend/src/database/entities/).
Tenant context helper: [backend/src/database/tenant-context.ts](../backend/src/database/tenant-context.ts).

### organizations
| column | type | notes |
|---|---|---|
| id | uuid | pk |
| name | text | e.g. "AXON Internal" |
| plan | text | nullable, future billing tier |
| created_at | timestamptz | default now() |

### users
| column | type | notes |
|---|---|---|
| id | uuid | pk |
| org_id | uuid | fk organizations(id) |
| email | citext | unique |
| password_hash | text | bcrypt, stubbed in v1 |
| role | text | `admin` \| `member` |
| created_at | timestamptz | |

### audits
| column | type | notes |
|---|---|---|
| id | uuid | pk |
| org_id | uuid | fk |
| brand_name | text | |
| status | text | queued \| resolving \| scraping \| scoring \| enriching \| rendering \| complete \| failed |
| started_at | timestamptz | |
| finished_at | timestamptz | nullable |
| score_total | int | nullable until scored |
| score_possible | int | accounts for `na` criteria |
| grade | text | A \| B \| C \| D \| F |
| report_pdf_gcs_path | text | `gs://bucket/{org_id}/{audit_id}.pdf` |
| version | int | increments on re-score |
| error_message | text | populated on failure |

### audit_brand_data
Brand-level scrape payload (one row per audit).

### audit_asins
One row per discovered ASIN.

### audit_reviews
One row per scraped review.

### audit_scores
Per-criterion score. `status ∈ (scored, na, warning)`. `evidence jsonb` carries the rationale payload.

### audit_findings
Strengths, weaknesses, recommendations, quick wins. `source ∈ (rule, llm)`.

### audit_manual_overrides
Values the user corrected on the Override screen. Retained for audit trail.

### audit_events
Drives the Progress screen. One row per pipeline stage transition or significant event.

### ai_usage_logs
Written by the AI Proxy. Per-call Claude cost tracking. See AI Proxy README for schema.

---

## Indexes

- `(org_id, started_at DESC)` on `audits` for the "recent audits" table.
- `(audit_id)` on every child table.
- `(org_id, created_at)` on `ai_usage_logs` for cost dashboards.
