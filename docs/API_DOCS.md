# AXON — API Documentation

Backend API surface for Tier 1 Brand Audit (v1).

Base URL (local): `http://localhost:4000/api`
Base URL (prod): TBD once Cloud Run is provisioned (T-02).

Auth: none in v1. v1.1 will add `Authorization: Bearer <jwt>`.

---

## Health

### `GET /health`
Liveness check.

**Response 200**
```json
{ "status": "ok", "service": "axon-backend", "version": "1.0.0" }
```

---

## Audits (T-05 — not yet implemented)

### `POST /audits`
Start a new Brand Audit Tier 1.

**Request**
```json
{ "brandName": "Anker" }
```

**Response 202**
```json
{ "auditId": "6fa5c...", "status": "queued" }
```

### `GET /audits/:id`
Get current audit state and scoring (once complete).

### `GET /audits/:id/events` — SSE
Server-Sent Events stream for the Progress screen.

### `GET /audits/:id/pdf`
Returns a 15-minute signed GCS URL for the generated PDF.

### `POST /audits/:id/overrides`
Submit value corrections and trigger a scoring-only re-run. Bumps `audits.version`.

### `GET /audits`
List audits for the current org (newest first, paginated).
