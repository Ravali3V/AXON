"""AXON AI Proxy — FastAPI entrypoint.

Every Claude call in the AXON platform routes through this service. The proxy:
  1. enriches the request with metadata (org_id, audit_id, purpose),
  2. forwards to Anthropic (or returns a canned stub response if no key),
  3. extracts usage, computes cost,
  4. writes ai_usage_logs BEFORE returning to the caller,
  5. enforces a per-audit cost cap (denies when exceeded).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .config import get_settings
from .db import close_pool, get_pool
from .routes import claude as claude_route

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm up the pool so the first /v1/messages call isn't slow.
    try:
        await get_pool()
        log.info("ai_proxy_started", stub_mode=get_settings().stub_mode)
    except Exception as exc:  # pragma: no cover — integration tested
        log.warning("db_pool_unavailable_at_startup", error=str(exc))
    yield
    await close_pool()


app = FastAPI(
    title="AXON AI Proxy",
    version="1.0.0",
    description="Centralized Claude proxy with cost tracking.",
    lifespan=lifespan,
)

app.include_router(claude_route.router, prefix="/v1")


@app.get("/health")
async def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "axon-ai-proxy",
        "version": "1.0.0",
        "stub_mode": settings.stub_mode,
    }
