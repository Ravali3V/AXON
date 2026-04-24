"""AXON Worker bootstrap — Windows-safe entrypoint.

Reason this exists:
    On Windows, asyncio.create_subprocess_exec (used by Playwright to launch
    Chromium) requires ProactorEventLoop. uvicorn.run() internally creates its
    own event loop, ignoring any previously set policy.

    The fix: bypass uvicorn.run() and instead create a ProactorEventLoop
    explicitly, then run uvicorn's Server coroutine directly on it. This
    guarantees Playwright always gets ProactorEventLoop regardless of how
    uvicorn manages its internal loop.

Usage:
    cd worker
    python run.py
"""

from __future__ import annotations

import asyncio
import io
import sys

# On Windows, stdout/stderr default to cp1252 which can't encode most Unicode
# characters found in scraped Amazon content. Force UTF-8 for all log output.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main() -> None:
    import uvicorn

    config = uvicorn.Config(
        "src.main:app",
        host="0.0.0.0",
        port=9090,
        reload=False,
    )
    server = uvicorn.Server(config)

    if sys.platform == "win32":
        # Explicitly create ProactorEventLoop — the only loop on Windows that
        # supports asyncio.create_subprocess_exec (required by Playwright).
        loop = asyncio.ProactorEventLoop()  # type: ignore[attr-defined]
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
