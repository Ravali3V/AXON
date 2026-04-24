"""Master pipeline: brand -> resolve -> discover ASINs -> scrape PDPs -> scrape brand
store/story/reviews -> score -> enrich via AI Proxy -> render PDF.

In v1, stages T-07/T-08/T-09/T-10/T-11 are still stubs — this file is the
coordination skeleton that exists now so T-06's discovery pipeline has a home.
Each later task fills in its own stage.
"""

from __future__ import annotations

import asyncio

import structlog

from ..config import get_settings
from ..db import emit_event, set_audit_status
from ..enrichment.enricher import enrich_audit
from ..scoring.engine import score_audit
from ..scrape.asin_discovery import discover_asins
from ..scrape.brand_resolver import BrandResolution, resolve_brand, sanitize_brand_name
from ..scrape.brand_store import scrape_brand_store, write_brand_store_snapshot
from ..scrape.browser import CaptchaDetected, audit_session, new_page
from ..scrape.executor import run_bounded
from ..scrape.pdp_scraper import AsinSnapshot, scrape_pdp, write_asin_snapshot
from ..scrape.reviews import (
    count_reviews_for_audit,
    scrape_reviews_for_asin_on_page,
    write_reviews,
)

log = structlog.get_logger(__name__)


async def run_audit(*, audit_id: str, org_id: str, brand_name: str) -> None:
    """Run the full Tier 1 audit pipeline. Writes progress events + final status.

    Wraps everything in an `audit_session` so every browser tab opened by any
    stage (resolver, discovery, PDP, brand store, reviews) shares ONE context
    and ONE cookie jar — Amazon sees a single continuous browsing session.
    """
    async with audit_session(audit_id):
        await _run_audit_inner(audit_id=audit_id, org_id=org_id, brand_name=brand_name)


async def _run_audit_inner(*, audit_id: str, org_id: str, brand_name: str) -> None:
    try:
        # Sanitize user input (drop trailing punctuation like "warmies." -> "warmies")
        brand_name = sanitize_brand_name(brand_name) or brand_name

        await set_audit_status(org_id=org_id, audit_id=audit_id, status="resolving")
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="resolve_brand",
            message=f"Resolving brand '{brand_name}' on Amazon",
        )

        resolution = await _resolve_with_retries(brand_name, org_id=org_id, audit_id=audit_id)

        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="resolve_brand",
            message=(
                f"Resolved. Search URL: {resolution.search_url}. "
                f"Brand Store: {'yes' if resolution.brand_store_url else 'no'}."
            ),
        )

        settings = get_settings()
        await set_audit_status(org_id=org_id, audit_id=audit_id, status="scraping")
        discovery_url = resolution.filtered_search_url or resolution.search_url
        discovery = await discover_asins(
            start_url=discovery_url,
            org_id=org_id,
            audit_id=audit_id,
        )
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="discover_asins",
            message=(
                f"Discovery complete: {len(discovery.asins)} ASINs across "
                f"{discovery.pages_visited} pages."
            ),
        )

        # Apply test limit if configured — easy to remove by unsetting AUDIT_TEST_ASIN_LIMIT.
        asins_to_process = discovery.asins
        if settings.audit_test_asin_limit is not None and len(asins_to_process) > settings.audit_test_asin_limit:
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="discover_asins",
                message=(
                    f"TEST MODE: processing first {settings.audit_test_asin_limit} of "
                    f"{len(discovery.asins)} ASINs (set AUDIT_TEST_ASIN_LIMIT=0 to disable)."
                ),
                level="warn",
            )
            asins_to_process = asins_to_process[: settings.audit_test_asin_limit]

        # ---- T-07: per-ASIN PDP scrape ----
        if asins_to_process:
            await _scrape_pdps(
                audit_id=audit_id,
                org_id=org_id,
                asins=asins_to_process,
            )
        else:
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="scrape_pdp",
                message="No ASINs discovered — skipping PDP scrape.",
                level="warn",
            )

        # ---- T-08: Brand Store + Brand Story + reviews ----
        # Fallback: if brand_resolver didn't find a store URL from the search page,
        # check if any scraped PDP has a "Visit the X Store" byline link.
        if not resolution.brand_store_url and asins_to_process:
            fallback_url = await _find_store_url_from_pdps(audit_id=audit_id, org_id=org_id)
            if fallback_url:
                await emit_event(
                    org_id=org_id,
                    audit_id=audit_id,
                    stage="scrape_brand_store",
                    message=f"Brand Store URL found via PDP byline fallback: {fallback_url}",
                )
                resolution = BrandResolution(
                    brand_name_query=resolution.brand_name_query,
                    search_url=resolution.search_url,
                    brand_store_url=fallback_url,
                    filtered_search_url=resolution.filtered_search_url,
                )

        await _scrape_brand_store_stage(
            audit_id=audit_id,
            org_id=org_id,
            resolution=resolution,
        )

        if asins_to_process:
            await _scrape_reviews_stage(
                audit_id=audit_id,
                org_id=org_id,
                asins=asins_to_process,
            )

        # ---- T-09: scoring ----
        await score_audit(audit_id=audit_id, org_id=org_id)

        # ---- T-10: LLM enrichment ----
        await enrich_audit(audit_id=audit_id, org_id=org_id)

        # ---- T-11: PDF render (imported lazily to avoid circular) ----
        from ..pdf.renderer import render_and_upload
        await set_audit_status(org_id=org_id, audit_id=audit_id, status="rendering")
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="render_pdf",
            message="Rendering branded PDF report.",
        )
        pdf_path = await render_and_upload(audit_id=audit_id, org_id=org_id)
        await set_audit_status(
            org_id=org_id,
            audit_id=audit_id,
            status="complete",
            report_pdf_gcs_path=pdf_path,
        )
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="complete",
            message=f"Audit complete. PDF: {pdf_path}",
        )
        return

    except CaptchaDetected as exc:
        log.error("captcha_aborted_audit", audit_id=audit_id, url=exc.url)
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="captcha",
            message=f"Amazon robot-check fired at {exc.url}; audit failed. Add residential proxy credentials to .env and retry.",
            level="error",
        )
        await set_audit_status(
            org_id=org_id,
            audit_id=audit_id,
            status="failed",
            error_message="CAPTCHA / robot-check triggered.",
        )
    except Exception as exc:
        log.exception("audit_failed", audit_id=audit_id)
        # Many Playwright exceptions stringify to "" — include the class + repr so
        # the Progress screen shows something useful even then.
        err_type = type(exc).__name__
        err_repr = repr(exc)
        err_msg = str(exc) or err_repr
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="error",
            message=f"Audit failed ({err_type}): {err_msg}",
            level="error",
        )
        await set_audit_status(
            org_id=org_id,
            audit_id=audit_id,
            status="failed",
            error_message=f"{err_type}: {err_msg}",
        )


async def _scrape_pdps(*, audit_id: str, org_id: str, asins: list[str]) -> None:
    """Scrape every ASIN concurrently (bounded) and persist snapshots."""
    settings = get_settings()
    total = len(asins)
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scrape_pdp",
        message=f"Scraping {total} PDPs with concurrency {settings.scrape_max_concurrency_per_audit}",
    )

    completed = 0
    lock = asyncio.Lock()

    async def _one(asin: str) -> AsinSnapshot:
        nonlocal completed
        snap = await scrape_pdp(asin, org_id=org_id, audit_id=audit_id)
        await write_asin_snapshot(org_id=org_id, audit_id=audit_id, snapshot=snap)
        async with lock:
            completed += 1
            # Emit every 10 ASINs (or the last one) so the Progress screen has a heartbeat.
            if completed % 10 == 0 or completed == total:
                await emit_event(
                    org_id=org_id,
                    audit_id=audit_id,
                    stage="scrape_pdp",
                    message=f"PDP progress: {completed}/{total}",
                )
        return snap

    results = await run_bounded(
        asins,
        _one,
        max_concurrency=settings.scrape_max_concurrency_per_audit,
    )

    failures = [
        r for r in results if isinstance(r, AsinSnapshot) and not r.scrape_success
    ] + [r for r in results if isinstance(r, BaseException)]

    if failures:
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="scrape_pdp",
            message=f"{len(failures)} of {total} PDPs failed to scrape cleanly.",
            level="warn" if len(failures) < total else "error",
        )


async def _scrape_brand_store_stage(
    *,
    audit_id: str,
    org_id: str,
    resolution: BrandResolution,
) -> None:
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scrape_brand_store",
        message=(
            f"Scraping Brand Store: {resolution.brand_store_url or 'none detected'}"
        ),
    )
    snapshot = await scrape_brand_store(
        store_url=resolution.brand_store_url,
        org_id=org_id,
        audit_id=audit_id,
    )
    await write_brand_store_snapshot(org_id=org_id, audit_id=audit_id, snapshot=snapshot)
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scrape_brand_store",
        message=(
            f"Brand Store: exists={snapshot.exists} pages={snapshot.page_count} "
            f"videos={snapshot.video_count} about_us={'yes' if snapshot.about_us_text else 'no'}"
        ),
    )


async def _scrape_reviews_stage(*, audit_id: str, org_id: str, asins: list[str]) -> None:
    """Scrape reviews using ONE shared warmed-up browser session — sequential per ASIN.

    Review pages are aggressively bot-protected.  Parallel fresh contexts get
    CAPTCHAed 100% of the time.  A single session that warmed up on the Amazon
    homepage, with realistic inter-request delays, passes through cleanly.
    """
    settings = get_settings()
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scrape_reviews",
        message=(
            f"Sampling reviews across {len(asins)} ASINs — sequential shared session "
            f"(hard cap {settings.audit_hard_review_ceiling})"
        ),
    )

    total_collected = 0
    warned_soft = False

    async with new_page(settings) as page:
        # Warm up with homepage first so the session has real Amazon cookies.
        try:
            await page.goto(settings.amazon_base_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.0)
        except Exception:
            pass  # non-fatal

        for asin in asins:
            if total_collected >= settings.audit_hard_review_ceiling:
                break

            reviews = await scrape_reviews_for_asin_on_page(
                asin,
                page,
                org_id=org_id,
                audit_id=audit_id,
                remaining_budget=settings.audit_hard_review_ceiling - total_collected,
                settings=settings,
            )
            if reviews:
                await write_reviews(org_id=org_id, audit_id=audit_id, reviews=reviews)
                total_collected += len(reviews)

            if not warned_soft and total_collected >= settings.audit_soft_review_warning:
                warned_soft = True
                await emit_event(
                    org_id=org_id,
                    audit_id=audit_id,
                    stage="scrape_reviews",
                    message=(
                        f"Collected {total_collected} reviews so far (soft warning at "
                        f"{settings.audit_soft_review_warning}); continuing."
                    ),
                    level="warn",
                )

    final_count = await count_reviews_for_audit(org_id=org_id, audit_id=audit_id)
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scrape_reviews",
        message=f"Review sampling complete: {final_count} reviews captured.",
    )


async def _find_store_url_from_pdps(*, audit_id: str, org_id: str) -> str | None:
    """Scan raw PDP snapshots for a brand_store_url extracted from the byline link."""
    from ..db import with_tenant
    import asyncpg  # type: ignore[import-not-found]

    async def _query(conn: asyncpg.Connection) -> str | None:
        rows = await conn.fetch(
            "SELECT raw->>'brand_store_url' AS store_url FROM audit_asins WHERE audit_id = $1",
            audit_id,
        )
        for r in rows:
            url = r["store_url"]
            if url and "/stores/" in url:
                return url
        return None

    return await with_tenant(org_id, _query)


async def _resolve_with_retries(brand_name: str, *, org_id: str, audit_id: str, max_attempts: int = 3):
    """Retry brand resolution up to N times on CAPTCHA or network timeout."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await resolve_brand(brand_name)
        except CaptchaDetected as exc:
            last_exc = exc
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="resolve_brand",
                message=f"CAPTCHA on attempt {attempt}; rotating context.",
                level="warn",
            )
        except Exception as exc:
            last_exc = exc
            err_type = type(exc).__name__
            is_timeout = "timeout" in str(exc).lower() or "TimeoutError" in err_type
            hint = (
                " — Amazon may be blocking direct connections. "
                "Set PROXY_ENDPOINT / PROXY_USERNAME / PROXY_PASSWORD in .env to use a residential proxy."
                if is_timeout else ""
            )
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="resolve_brand",
                message=f"Brand resolution attempt {attempt} failed ({err_type}){hint}",
                level="warn",
            )
            if attempt == max_attempts:
                break
        await asyncio.sleep(2**attempt)
    assert last_exc is not None
    raise last_exc


async def run_rescore(*, audit_id: str, org_id: str, version: int) -> None:
    """Re-run scoring only (no scrape), applying manual overrides already written
    to audit_manual_overrides. The scoring engine reads audit_asins + audit_brand_data
    + audit_reviews as-is; T-14 will make overrides mutate those tables before
    calling back into scoring so the re-score reflects the user's corrections.
    """
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="rescore",
        message=f"Re-scoring v{version} using current snapshot + manual overrides.",
    )
    try:
        await score_audit(audit_id=audit_id, org_id=org_id)
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="rescore",
            message=f"Rescore v{version} complete.",
        )
    except Exception as exc:
        log.exception("rescore_failed", audit_id=audit_id)
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="rescore",
            message=f"Rescore failed: {exc}",
            level="error",
        )
        await set_audit_status(
            org_id=org_id,
            audit_id=audit_id,
            status="failed",
            error_message=str(exc),
        )
