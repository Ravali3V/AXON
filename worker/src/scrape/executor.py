"""Bounded-concurrency executor for scrape tasks.

Amazon doesn't reward parallelism — high fan-out triggers CAPTCHA. Config caps us at
`scrape_max_concurrency_per_audit` (default 4) simultaneous browser contexts per audit.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def run_bounded(
    items: list[T],
    fn: Callable[[T], Awaitable[R]],
    *,
    max_concurrency: int,
) -> list[R]:
    """Apply `fn` to every item with at most `max_concurrency` in flight.

    Results preserve input order. Exceptions are captured and returned as-is
    so one ASIN failing doesn't abort the rest.
    """
    sem = asyncio.Semaphore(max(1, max_concurrency))
    results: list[R | BaseException] = [None] * len(items)  # type: ignore[list-item]

    async def _runner(idx: int, item: T) -> None:
        async with sem:
            try:
                results[idx] = await fn(item)
            except BaseException as exc:  # noqa: BLE001
                results[idx] = exc

    await asyncio.gather(*[_runner(i, x) for i, x in enumerate(items)])
    return results  # type: ignore[return-value]
