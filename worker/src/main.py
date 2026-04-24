"""AXON Audit Worker — FastAPI entrypoint.

The worker accepts audit jobs from the backend (via Cloud Tasks in prod, direct HTTP in
dev) and runs the full pipeline: brand resolution -> ASIN discovery -> per-ASIN scrape
-> Brand Store / Brand Story / video / reviews -> scoring -> LLM enrichment -> PDF render.
"""

from __future__ import annotations

import asyncio
import sys

# Windows-only: Playwright launches Chromium via asyncio.create_subprocess_exec, which
# requires ProactorEventLoopPolicy. Uvicorn/FastAPI on Windows sometimes install a loop
# policy that lacks subprocess support (SelectorEventLoop raises NotImplementedError).
# Setting this at module import time — before uvicorn creates its event loop — fixes it.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .db import close_pool, get_pool
from .routes import audits as audits_route
from .scrape.browser import browser_pool

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await get_pool()
        log.info("worker_started")
    except Exception as exc:  # pragma: no cover
        log.warning("worker_db_unavailable", error=str(exc))
    yield
    await close_pool()
    await browser_pool.close()


app = FastAPI(
    title="AXON Audit Worker",
    version="1.0.0",
    description="Playwright scraper + scoring + enrichment + PDF rendering.",
    lifespan=lifespan,
)

app.include_router(audits_route.router, prefix="/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "axon-worker", "version": "1.0.0"}
