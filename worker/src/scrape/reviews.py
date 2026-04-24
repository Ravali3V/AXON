"""Review scraper — paginate /product-reviews/{asin}?pageNumber=N for each ASIN.

Captures rating, title, body, verified-purchase flag, and helpful-vote count. Writes
each review to audit_reviews. Sentiment classification is deferred to T-10 (Haiku).

Respects:
  - `audit_hard_review_ceiling` — absolute cap across all ASINs in the audit
  - `audit_soft_review_warning` — emits a warning at this threshold
  - `max_pages_per_asin` — soft cap per ASIN (default 20 pages = ~200 reviews)
"""

from __future__ import annotations

import asyncio
import urllib.parse as urlparse
from dataclasses import dataclass

import asyncpg  # type: ignore[import-not-found]
import structlog
from playwright.async_api import Page

from ..config import Settings, get_settings
from ..db import emit_event, with_tenant
from .browser import CaptchaDetected, new_page, polite_goto
from .parsers import clean_text, parse_rating
from .selectors import REVIEW

log = structlog.get_logger(__name__)


@dataclass
class ReviewRecord:
    asin: str
    review_id: str | None
    rating: int | None
    verified: bool
    helpful_votes: int
    title: str | None
    body: str | None


async def scrape_reviews_for_asin(
    asin: str,
    *,
    org_id: str,
    audit_id: str,
    max_pages: int = 20,
    already_collected: int = 0,
    settings: Settings | None = None,
) -> list[ReviewRecord]:
    """Single-ASIN entry point — creates its own browser context (used standalone)."""
    s = settings or get_settings()
    remaining_budget = s.audit_hard_review_ceiling - already_collected
    if remaining_budget <= 0:
        return []

    async with new_page(s) as page:
        return await _scrape_reviews_on_page(
            asin=asin,
            page=page,
            org_id=org_id,
            audit_id=audit_id,
            max_pages=max_pages,
            remaining_budget=remaining_budget,
            settings=s,
        )


async def scrape_reviews_for_asin_on_page(
    asin: str,
    page,
    *,
    org_id: str,
    audit_id: str,
    max_pages: int = 20,
    remaining_budget: int,
    settings: Settings | None = None,
) -> list[ReviewRecord]:
    """Shared-page variant — caller owns the page/context lifetime.

    Used by the pipeline stage which opens ONE warmed-up session and scrapes
    all ASINs sequentially through it, avoiding per-ASIN fresh-context CAPTCHAs.
    """
    s = settings or get_settings()
    return await _scrape_reviews_on_page(
        asin=asin,
        page=page,
        org_id=org_id,
        audit_id=audit_id,
        max_pages=max_pages,
        remaining_budget=remaining_budget,
        settings=s,
    )


async def _scrape_reviews_on_page(
    asin: str,
    page,
    *,
    org_id: str,
    audit_id: str,
    max_pages: int,
    remaining_budget: int,
    settings: Settings,
) -> list[ReviewRecord]:
    collected: list[ReviewRecord] = []
    base = settings.amazon_base_url

    for page_num in range(1, max_pages + 1):
        url = f"{base}/product-reviews/{asin}?{urlparse.urlencode({'pageNumber': page_num})}"
        try:
            await polite_goto(page, url, settings)
        except CaptchaDetected:
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="scrape_reviews",
                message=f"CAPTCHA on review page {page_num} for {asin}; stopping this ASIN.",
                level="warn",
            )
            break

        cards = await page.query_selector_all(", ".join(REVIEW["review_card"]))
        if not cards:
            break

        new_on_page = 0
        for card in cards:
            if len(collected) >= remaining_budget:
                break
            rec = await _extract_review(card, asin)
            if rec:
                collected.append(rec)
                new_on_page += 1

        if len(collected) >= remaining_budget:
            break
        if new_on_page == 0:
            break
        # Check for next page link.
        next_el = None
        for sel in REVIEW["pagination_next"]:
            next_el = await page.query_selector(sel)
            if next_el:
                break
        if not next_el:
            break

    return collected


async def _extract_review(card, asin: str) -> ReviewRecord | None:
    review_id = await card.get_attribute(REVIEW["review_id_attr"])
    title = clean_text(await _first_text_sub(card, REVIEW["review_title"]))
    body = clean_text(await _first_text_sub(card, REVIEW["review_body"]))

    # Rating: "4.0 out of 5 stars" — parse_rating returns float; cast to int star.
    rating_text = await _first_text_sub(card, REVIEW["review_stars"])
    rating_float = parse_rating(rating_text)
    rating = int(round(rating_float)) if rating_float is not None else None

    verified_el = None
    for sel in REVIEW["verified_badge"]:
        verified_el = await card.query_selector(sel)
        if verified_el:
            break
    verified = verified_el is not None

    helpful_votes = 0
    for sel in REVIEW["helpful_votes"]:
        hel = await card.query_selector(sel)
        if not hel:
            continue
        text = clean_text(await hel.text_content()) or ""
        # "47 people found this helpful" / "One person found this helpful"
        import re

        m = re.search(r"([0-9][0-9,]*)", text)
        if m:
            try:
                helpful_votes = int(m.group(1).replace(",", ""))
            except ValueError:
                helpful_votes = 0
        elif text.lower().startswith("one"):
            helpful_votes = 1
        break

    if not (title or body):
        return None

    return ReviewRecord(
        asin=asin,
        review_id=review_id,
        rating=rating,
        verified=verified,
        helpful_votes=helpful_votes,
        title=title,
        body=body,
    )


async def _first_text_sub(parent, selectors: list[str]) -> str | None:
    for sel in selectors:
        el = await parent.query_selector(sel)
        if el:
            t = await el.text_content()
            if t and t.strip():
                return t
    return None


async def write_reviews(
    *,
    org_id: str,
    audit_id: str,
    reviews: list[ReviewRecord],
) -> None:
    if not reviews:
        return

    async def _do(conn: asyncpg.Connection) -> None:
        await conn.executemany(
            """
            INSERT INTO audit_reviews (
                audit_id, org_id, asin, review_id, rating, verified, helpful_votes, title, body
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            [
                (
                    audit_id,
                    org_id,
                    r.asin,
                    r.review_id,
                    r.rating,
                    r.verified,
                    r.helpful_votes,
                    r.title,
                    r.body,
                )
                for r in reviews
            ],
        )

    await with_tenant(org_id, _do)


async def count_reviews_for_audit(*, org_id: str, audit_id: str) -> int:
    async def _count(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow(
            "SELECT COUNT(*)::int AS c FROM audit_reviews WHERE audit_id = $1",
            audit_id,
        )
        return int(row["c"]) if row else 0

    return await with_tenant(org_id, _count)
