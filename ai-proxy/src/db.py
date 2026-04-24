"""asyncpg connection pool + ai_usage_logs writer.

The proxy writes directly to Postgres (bypassing the NestJS API) so every Claude call is
accounted for even if the calling service forgets to update its own state. The write
happens BEFORE returning the response to the caller — if the log insert fails, the call
fails.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg  # type: ignore[import-not-found]
import structlog

from .config import get_settings

log = structlog.get_logger(__name__)


_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    """Lazily initialize a connection pool. Safe to call from multiple tasks."""
    global _pool
    if _pool is not None:
        return _pool

    async with _pool_lock:
        if _pool is None:
            settings = get_settings()
            _pool = await asyncpg.create_pool(
                dsn=settings.resolved_database_url,
                min_size=1,
                max_size=10,
                command_timeout=10,
            )
    assert _pool is not None
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def insert_ai_usage_log(*, entry: dict[str, Any]) -> None:
    """Insert one row into ai_usage_logs. Runs under the tenant's GUC so RLS is satisfied."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_org', $1, true)",
                entry["org_id"],
            )
            await conn.execute(
                """
                INSERT INTO ai_usage_logs (
                    org_id, audit_id, model, provider,
                    input_tokens, output_tokens, cost_usd, latency_ms,
                    purpose, success, error_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                entry["org_id"],
                entry.get("audit_id"),
                entry["model"],
                entry["provider"],
                entry.get("input_tokens", 0),
                entry.get("output_tokens", 0),
                entry.get("cost_usd", 0.0),
                entry.get("latency_ms", 0),
                entry.get("purpose", "other"),
                entry.get("success", True),
                entry.get("error_message"),
            )


async def audit_cost_to_date(*, org_id: str, audit_id: str) -> float:
    """Sum cost_usd for an audit so far. Used by the per-audit cost cap."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_org', $1, true)",
                org_id,
            )
            row = await conn.fetchrow(
                "SELECT COALESCE(SUM(cost_usd), 0)::float8 AS total "
                "FROM ai_usage_logs WHERE audit_id = $1",
                audit_id,
            )
    return float(row["total"]) if row else 0.0
