"""Per-ASIN Product Detail Page scraper.

Given an ASIN, fetch /dp/{asin} and extract every data point that feeds the 100-point
rubric:
  - title, bullets, description
  - image count (+ whether main image meets Amazon's white-bg ≥1000px guide)
  - A+ Content presence + module count
  - Brand Story carousel presence
  - Video module presence
  - rating, review count
  - BSR (rank + category)
  - Buy Box seller
  - price
  - variation parent (if part of a variation family)

Writes one row to audit_asins per ASIN. Emits progress events. Retries on CAPTCHA
with a fresh browser context (+ rotated proxy if configured) up to 3 attempts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

import asyncpg  # type: ignore[import-not-found]
import structlog
from playwright.async_api import Page

from ..config import Settings, get_settings
from ..db import emit_event, with_tenant
from .browser import CaptchaDetected, new_page, polite_goto
from .parsers import (
    clean_text,
    parse_bsr,
    parse_price,
    parse_rating,
    parse_review_count,
)
from .selectors import PDP

log = structlog.get_logger(__name__)


@dataclass
class AsinSnapshot:
    """Flat record ready to be written to audit_asins."""

    asin: str
    title: str | None = None
    bullets: list[str] | None = None
    description: str | None = None
    price: str | None = None  # numeric stringified so asyncpg treats as NUMERIC
    bsr: int | None = None
    bsr_category: str | None = None
    rating: float | None = None
    review_count: int | None = None
    image_count: int = 0
    main_image_url: str | None = None
    bullet_count: int = 0
    has_aplus: bool = False
    aplus_module_count: int = 0
    has_brand_story: bool = False
    has_video: bool = False
    buybox_seller: str | None = None
    brand_store_url: str | None = None
    variation_parent_asin: str | None = None
    scrape_success: bool = True
    scrape_error: str | None = None


async def scrape_pdp(
    asin: str,
    *,
    org_id: str,
    audit_id: str,
    settings: Settings | None = None,
    max_attempts: int = 3,
) -> AsinSnapshot:
    s = settings or get_settings()
    url = f"{s.amazon_base_url}/dp/{asin}"
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with new_page(s) as page:
                await polite_goto(page, url, s)
                snap = await _extract(page, asin)
                return snap
        except CaptchaDetected as exc:
            last_exc = exc
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="scrape_pdp",
                message=f"CAPTCHA on ASIN {asin} attempt {attempt}; retrying with fresh context.",
                level="warn",
            )
        except Exception as exc:  # network glitch, timeout — retry a couple of times
            last_exc = exc
            log.warning("pdp_scrape_attempt_failed", asin=asin, attempt=attempt, error=str(exc))

    # All attempts exhausted — return a failure snapshot so scoring can mark `warning`.
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scrape_pdp",
        message=f"PDP scrape failed for {asin} after {max_attempts} attempts: {last_exc}",
        level="error",
    )
    return AsinSnapshot(
        asin=asin,
        scrape_success=False,
        scrape_error=str(last_exc) if last_exc else "unknown",
    )


async def _extract(page: Page, asin: str) -> AsinSnapshot:
    """Extract all rubric data points from a loaded PDP."""
    title = clean_text(await _first_text(page, PDP["title"]))

    # Bullets
    bullets_els = await page.query_selector_all(", ".join(PDP["bullets"]))
    bullets_raw = []
    for el in bullets_els[:15]:  # cap to protect against runaway extraction
        t = clean_text(await el.text_content())
        if t and len(t) > 3:
            bullets_raw.append(t)
    # Amazon sometimes embeds the first bullet as a "Make sure this fits" banner — drop it.
    bullets = [b for b in bullets_raw if "fits your" not in b.lower()]

    description = clean_text(await _first_text(page, PDP["description"]))

    # Price
    price_raw = await _first_text(page, PDP["price"])
    price_dec = parse_price(price_raw)
    price_str = str(price_dec) if price_dec is not None else None

    # Images
    img_els = await page.query_selector_all(", ".join(PDP["images"]))
    image_count = len(img_els)
    main_image_url = await _first_attr(page, PDP["main_image"], "src") or await _first_attr(
        page, PDP["main_image"], "data-old-hires"
    )

    # A+ Content
    aplus_el = await _first_element(page, PDP["aplus"])
    has_aplus = aplus_el is not None
    aplus_modules = 0
    if has_aplus:
        modules = await page.query_selector_all(", ".join(PDP["aplus_modules"]))
        aplus_modules = len(modules)

    # Brand Story
    brand_story_el = await _first_element(page, PDP["brand_story"])
    has_brand_story = brand_story_el is not None

    # Video
    video_el = await _first_element(page, PDP["video"])
    has_video = video_el is not None

    # Rating
    rating_text = await _first_text(page, PDP["rating_value"])
    rating = parse_rating(rating_text)

    # Review count
    rc_text = await _first_text(page, PDP["review_count_link"])
    review_count = parse_review_count(rc_text)

    # BSR — gather text across matching row selectors
    bsr_rank, bsr_category = await _extract_bsr(page)

    # Buy Box seller
    buybox_seller = clean_text(await _first_text(page, PDP["buybox_seller"]))

    # Brand Store URL — extract from "Visit the X Store" byline link
    brand_store_url: str | None = None
    byline_el = await _first_element(page, PDP["byline_store_link"])
    if byline_el:
        href = await byline_el.get_attribute("href")
        if href and "/stores/" in href:
            if href.startswith("/"):
                href = "https://www.amazon.com" + href
            brand_store_url = href.split("?")[0]  # strip tracking params

    # Variation — if a `#twister` or variation widget is present, the ASIN is a child.
    variation_parent_asin = None
    variation_widget = await _first_element(page, PDP["variation_parent"])
    if variation_widget:
        # We don't have the parent ASIN directly without more pages; record that this
        # ASIN is PART OF a variation family by setting parent to itself's group key.
        variation_parent_asin = f"family:{asin}"

    return AsinSnapshot(
        asin=asin,
        title=title,
        bullets=bullets,
        description=description,
        price=price_str,
        bsr=bsr_rank,
        bsr_category=bsr_category,
        rating=rating,
        review_count=review_count,
        image_count=image_count,
        main_image_url=main_image_url,
        bullet_count=len(bullets),
        has_aplus=has_aplus,
        aplus_module_count=aplus_modules,
        has_brand_story=has_brand_story,
        has_video=has_video,
        buybox_seller=buybox_seller,
        brand_store_url=brand_store_url,
        variation_parent_asin=variation_parent_asin,
    )


async def _extract_bsr(page: Page) -> tuple[int | None, str | None]:
    """Look for Best Sellers Rank across the detail-bullet variants."""
    for row_sel in PDP["bsr_rows"]:
        rows = await page.query_selector_all(row_sel)
        for row in rows:
            txt = (await row.text_content()) or ""
            if PDP["bsr_text_match"] in txt:
                rank, category = parse_bsr(txt)
                if rank:
                    return rank, category
    return None, None


async def _first_text(page: Page, selectors: list[str]) -> str | None:
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            t = await el.text_content()
            if t and t.strip():
                return t
    return None


async def _first_attr(page: Page, selectors: list[str], attr: str) -> str | None:
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            v = await el.get_attribute(attr)
            if v:
                return v
    return None


async def _first_element(page: Page, selectors: list[str]):
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            return el
    return None


async def write_asin_snapshot(
    *,
    org_id: str,
    audit_id: str,
    snapshot: AsinSnapshot,
) -> None:
    """Upsert an AuditAsin row. Re-scrapes overwrite existing snapshots for the same ASIN."""

    async def _do(conn: asyncpg.Connection) -> None:
        raw_payload = json.dumps(asdict(snapshot))
        await conn.execute(
            """
            INSERT INTO audit_asins (
                audit_id, org_id, asin, title, price, bsr, bsr_category,
                rating, review_count, image_count, bullet_count,
                has_aplus, has_brand_story, has_video, buybox_seller,
                variation_parent_asin, raw
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17::jsonb)
            ON CONFLICT (audit_id, asin) DO UPDATE SET
                title = EXCLUDED.title,
                price = EXCLUDED.price,
                bsr = EXCLUDED.bsr,
                bsr_category = EXCLUDED.bsr_category,
                rating = EXCLUDED.rating,
                review_count = EXCLUDED.review_count,
                image_count = EXCLUDED.image_count,
                bullet_count = EXCLUDED.bullet_count,
                has_aplus = EXCLUDED.has_aplus,
                has_brand_story = EXCLUDED.has_brand_story,
                has_video = EXCLUDED.has_video,
                buybox_seller = EXCLUDED.buybox_seller,
                variation_parent_asin = EXCLUDED.variation_parent_asin,
                raw = EXCLUDED.raw
            """,
            audit_id,
            org_id,
            snapshot.asin,
            snapshot.title,
            snapshot.price,
            snapshot.bsr,
            snapshot.bsr_category,
            snapshot.rating,
            snapshot.review_count,
            snapshot.image_count,
            snapshot.bullet_count,
            snapshot.has_aplus,
            snapshot.has_brand_story,
            snapshot.has_video,
            snapshot.buybox_seller,
            snapshot.variation_parent_asin,
            raw_payload,
        )

    await with_tenant(org_id, _do)
