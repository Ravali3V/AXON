# AXON — Claude Standing Instructions

These rules apply to every session. Follow them without being asked.

---

## Session Start

At the start of every session, do all of the following before writing any code:

1. Read `D:\Projects\BUILD.md` — New App Pipeline (Stages 0–8), Enhancement Pipeline (E1–E5), and sizing rules.
2. Read `docs/DESIGN_DECISIONS.md` — all product decisions and rationale.
3. Read `docs/FEATURES.md` — feature registry (built, planned, rejected).
4. Check `docs/plans/` (not `docs/plans/archive/`) for any active PLAN files. If found,
   read them and resume from where the last session left off.
5. Run `git status` to check for uncommitted changes from a previous session.
6. Run the full test suite to confirm a green baseline:
   ```
   pnpm --filter backend test && cd worker && .venv/Scripts/python -m pytest tests/ -q && cd ../ai-proxy && .venv/Scripts/python -m pytest tests/ -q
   ```
   If any tests fail, flag it to the user before proceeding. Do not write new code
   on top of a broken baseline.

---

## Pipeline — Every Change Goes Through It

Any change that touches an API endpoint, DB schema, UI workflow, or business logic
MUST go through the pipeline automatically. The user does not need to say "read BUILD.md".

Before starting any enhancement or new feature, read the Orchestrator Agent:
`D:\Projects\agents\orchestrator_agent.md`

The Orchestrator classifies the change (Hot-fix / Small / Medium / Large), determines
which stages are needed, enforces approval gates, and activates agents in order.

Do not skip stages. Respect every approval gate.

---

## Non-Negotiable Constraints (from Day 1)

These cannot be violated, even in a prototype:

1. **AI Proxy** — every Claude call routes through `ai-proxy/`. No direct `anthropic` SDK
   imports outside that service. `ai_usage_logs` must be written before the proxy returns.
2. **Multi-tenant isolation** — every tenant table has `org_id`, every query runs under
   `SET LOCAL app.current_org = <uuid>`, every RLS policy enforces it. Even with no login
   in v1, the plumbing must be real.
3. **Human approval for AI suggestions** — no auto-apply. Every AI recommendation flows
   through an approve / modify / reject path.
4. **Amazon guidelines are hard constraints** — no learned rule, suggestion, or generated
   content may violate Amazon ToS.
5. **No third-party auth / BaaS** — Custom JWT (bcrypt) only. No Firebase, no Supabase,
   no Auth0, no Clerk.
6. **No third-party data APIs** in v1 — no Keepa, no Helium 10, no Rainforest, no
   Jungle Scout. All Amazon data comes from our own Playwright scraper.

---

## Documentation Rules

Keep these docs current. Update them in the same session as the code change, before committing.

- `docs/API_DOCS.md` — when endpoints, request/response shapes, or auth change
- `docs/DATABASE.md` — when tables, columns, or statuses change
- `docs/USER_GUIDE.md` — when user-facing screens or workflows change
- `docs/DESIGN_DECISIONS.md` — when a new product decision is made
- `docs/FEATURES.md` — when features are planned / built / rejected
- `RELEASE_NOTES.md` — every version bump

---

## Code Rules

- Never hardcode secrets, API keys, or passwords. All secrets via env vars or Secret Manager.
- Follow existing patterns and conventions in the codebase.
- Do not add new statuses/enums without updating both DATABASE.md and FEATURES.md.
- TypeScript strict mode across `frontend/` and `backend/`.
- Python: type hints everywhere, `ruff` + `black` pre-commit. Python 3.11.
- Every new module in `worker/` must be callable in isolation (no hidden coupling to the pipeline orchestrator).
- Amazon selector changes go ONLY in `worker/src/scrape/selectors.py` — never inline.

---

## Database Migrations

- Migrations live in `infra/migrations/` and run via TypeORM.
- When adding, removing, or renaming columns or tables, create a migration.
- Every new tenant table must declare an RLS policy in the same migration.
- Review the generated migration before running it.
- For production: run migrations against Cloud SQL BEFORE deploying code that depends on the schema change.
- Never modify a migration already applied to production — create a new one instead.

---

## Deployment Rules

- Always ask "Shall I deploy?" before deploying to production. Never deploy without explicit user approval.
- When a new env var is introduced, add it to GCP Secret Manager / Cloud Run env config before deploying.
- When a migration exists, run it against Cloud SQL before deploying the code that depends on it.
- After deploying, verify the live URL is accessible before closing the session.
- If deployment fails: explain what went wrong in plain English, do not retry blindly, ask how to proceed.

---

## Commit Rules

- Run the full test suite before every commit. Never commit code that fails any test.
- Push to the remote after every commit. Do not wait to be asked.
- Update all relevant docs before committing.
- Never commit secrets or `.env` files.
- Always commit docs changes in the same commit as the code change that triggered them.

### Pre-Commit Checklist — MANDATORY

```
PRE-COMMIT CHECKLIST
--------------------------------------------
[ ] Tests run — all passing (paste count)
[ ] Version bumped in VERSION + frontend/package.json (per BUILD.md versioning rules)
[ ] RELEASE_NOTES.md updated (or confirmed no user-facing change)
[ ] FEATURES.md updated (or confirmed no new/changed feature)
[ ] DESIGN_DECISIONS.md updated (or confirmed no new decision)
[ ] USER_GUIDE.md updated (or confirmed no UI/workflow change)
[ ] API_DOCS.md updated (or confirmed no endpoint change)
[ ] DATABASE.md updated (or confirmed no schema change)
[ ] ai_usage_logs and audit_events write paths untouched or explicitly reviewed
[ ] Doc changes included in this same commit
--------------------------------------------
```

---

## Testing Rules

- Backend: Jest (NestJS), tests co-located as `*.spec.ts` + `backend/test/` for e2e.
- Worker & AI Proxy: pytest, tests under `worker/tests/` and `ai-proxy/tests/`.
- Frontend: Vitest + React Testing Library, tests co-located as `*.test.tsx`.

Write or update tests **before** writing implementation code (TDD — enforced by Stage 4 Testing Agent).

### When to Write New Tests

- A new endpoint — happy path + at least one error case + tenant-isolation rejection.
- A new scraper selector — fixture HTML + expected parsed output.
- A new scoring criterion — one "earns full points" case + one "zero/warning" case.
- A new pure function (parsers, validators, cost calc) — unit tests, no mocking.
- A new business rule — at least one positive and one negative test.

### When to Update Existing Tests

- Endpoint shape or status code changes.
- Rubric weights / thresholds change.
- Auth / tenant-scoping rules change.

### Tenant Isolation Test — Always Runs

Every CI build runs a job that attempts to read `audits` / `audit_scores` / etc. with a
wrong `org_id` and asserts zero rows returned. A failure here blocks deploy.

---

## Session End

- Commit any pending changes (code + docs together).
- Push to remote.
- If a feature is mid-flight, note the current stage (Stage 0–8 or E1–E5) and what
  remains in the PLAN file under `docs/plans/`.
- Update `D:\Projects\memory\axon.md` if any project facts changed: test count,
  deployment URLs, status, version, migration history, active prospect brands.
- Update workspace `D:\Projects\memory\MEMORY.md` only if AXON's status, version, or URLs changed.
