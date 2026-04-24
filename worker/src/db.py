"""asyncpg connection pool shared across worker modules.

All writes from the worker (audit_events, audit_brand_data, audit_asins, audit_reviews,
audit_scores, audit_findings) go through this pool and MUST run under `app.current_org`
so RLS is satisfied.

Use `with_tenant(pool, org_id, async_fn)` from orchestrator code.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import asyncpg  # type: ignore[import-not-found]
import structlog

from .config import get_settings

log = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()

T = TypeVar("T")


async def _init_conn(conn: asyncpg.Connection) -> None:
    # asyncpg returns JSONB/JSON as raw strings by default; register codecs so
    # columns come back as Python dicts/lists. format='text' is required in
    # asyncpg >= 0.27 for the decoder to be called.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
        format="text",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
        format="text",
    )


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            settings = get_settings()
            _pool = await asyncpg.create_pool(
                dsn=settings.resolved_database_url,
                min_size=1,
                max_size=8,
                command_timeout=30,
                init=_init_conn,
            )
    assert _pool is not None
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def with_tenant(org_id: str, fn: Callable[[asyncpg.Connection], Awaitable[T]]) -> T:
    """Run `fn` inside a transaction with `app.current_org = org_id`."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_org', $1, true)", org_id)
            return await fn(conn)


async def emit_event(
    *,
    org_id: str,
    audit_id: str,
    stage: str,
    message: str,
    level: str = "info",
) -> None:
    """Append a progress event. Drives the frontend Progress screen via SSE."""
    async def _insert(conn: asyncpg.Connection) -> None:
        await conn.execute(
            "INSERT INTO audit_events (org_id, audit_id, stage, message, level) VALUES ($1,$2,$3,$4,$5)",
            org_id,
            audit_id,
            stage,
            message,
            level,
        )
    await with_tenant(org_id, _insert)
    log.info("audit_event", audit_id=audit_id, stage=stage, message=message, level=level)


async def set_audit_status(
    *,
    org_id: str,
    audit_id: str,
    status: str,
    error_message: str | None = None,
    score_total: int | None = None,
    score_possible: int | None = None,
    grade: str | None = None,
    report_pdf_gcs_path: str | None = None,
) -> None:
    """Update audits.status + terminal fields. Idempotent."""
    async def _update(conn: asyncpg.Connection) -> None:
        finished = status in ("complete", "failed")
        await conn.execute(
            """
            UPDATE audits
            SET status = $2,
                error_message = COALESCE($3, error_message),
                score_total = COALESCE($4, score_total),
                score_possible = COALESCE($5, score_possible),
                grade = COALESCE($6, grade),
                report_pdf_gcs_path = COALESCE($7, report_pdf_gcs_path),
                finished_at = CASE WHEN $8 THEN now() ELSE finished_at END
            WHERE id = $1
            """,
            audit_id,
            status,
            error_message,
            score_total,
            score_possible,
            grade,
            report_pdf_gcs_path,
            finished,
        )
    await with_tenant(org_id, _update)
