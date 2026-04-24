"""Brand Store crawler.

Given a Brand Store URL (discovered during brand resolution), capture:
  - existence (if no URL was found, emit a `warning` finding later)
  - page count (number of sub-pages)
  - hero section presence + custom-imagery signal
  - video count
  - navigation depth
  - About Us / Brand Story text (if embedded in the store)

Writes one row to audit_brand_data per audit.
"""

from __future__ import annotations

import json
import urllib.parse as urlparse
from dataclasses import dataclass, field

import asyncpg  # type: ignore[import-not-found]
import structlog
from playwright.async_api import Page

from ..config import Settings, get_settings
from ..db import emit_event, with_tenant
from .browser import CaptchaDetected, new_page, polite_goto
from .parsers import clean_text
from .selectors import BRAND_STORE

log = structlog.get_logger(__name__)


@dataclass
class BrandStoreSnapshot:
    store_url: str | None
    exists: bool = False
    page_count: int = 0
    has_hero: bool = False
    video_count: int = 0
    nav_depth: int = 0
    about_us_text: str | None = None
    product_tile_count: int = 0
    brand_story_present: bool = False
    pages_visited: list[str] = field(default_factory=list)


async def scrape_brand_store(
    *,
    store_url: str | None,
    org_id: str,
    audit_id: str,
    settings: Settings | None = None,
    max_subpages: int = 10,
    max_attempts: int = 3,
) -> BrandStoreSnapshot:
    s = settings or get_settings()
    snap = BrandStoreSnapshot(store_url=store_url)
    if not store_url:
        return snap

    snap.exists = True
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with new_page(s) as page:
                await polite_goto(page, store_url, s)
                await _capture_landing(page, snap)
                await _crawl_subpages(page, snap, store_url, s, max_subpages)
            return snap
        except CaptchaDetected as exc:
            last_exc = exc
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="scrape_brand_store",
                message=f"CAPTCHA on Brand Store attempt {attempt}; retrying.",
                level="warn",
            )
        except Exception as exc:
            last_exc = exc
            log.warning("brand_store_scrape_failed", url=store_url, attempt=attempt, error=str(exc))

    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scrape_brand_store",
        message=f"Brand Store scrape failed after {max_attempts} attempts: {last_exc}",
        level="error",
    )
    return snap


async def _capture_landing(page: Page, snap: BrandStoreSnapshot) -> None:
    # Hero presence
    hero_el = await _first_element(page, BRAND_STORE["hero"])
    snap.has_hero = hero_el is not None

    # Videos — on the landing page
    videos = await page.query_selector_all(", ".join(BRAND_STORE["videos"]))
    snap.video_count += len(videos)

    # Navigation depth — count unique nav items
    nav_items = await page.query_selector_all(", ".join(BRAND_STORE["navigation_items"]))
    snap.nav_depth = max(snap.nav_depth, len(nav_items))

    # Product tiles on the landing page
    tiles = await page.query_selector_all(", ".join(BRAND_STORE["product_tiles"]))
    snap.product_tile_count += len(tiles)

    # Try to capture about-us text — Brand Stores often include an About section.
    html = await page.content()
    about = _extract_about_section(html)
    if about:
        snap.about_us_text = about
        snap.brand_story_present = True

    snap.pages_visited.append(page.url)
    snap.page_count = len(snap.pages_visited)


async def _crawl_subpages(
    page: Page,
    snap: BrandStoreSnapshot,
    start_url: str,
    settings: Settings,
    max_subpages: int,
) -> None:
    """Walk up to `max_subpages` sub-pages of the Brand Store to gather breadth signals."""
    # Get sub-page URLs from any detected pagination / nav list.
    sub_urls: list[str] = []
    # Try pagination tabs first
    page_tabs = await page.query_selector_all(", ".join(BRAND_STORE["page_count"]))
    for t in page_tabs:
        href = await t.get_attribute("href")
        if href:
            abs_url = _absolute(href, settings.amazon_base_url)
            if abs_url and abs_url not in snap.pages_visited and abs_url != start_url:
                sub_urls.append(abs_url)

    # Also sample links from navigation
    nav_items = await page.query_selector_all(", ".join(BRAND_STORE["navigation_items"]))
    for el in nav_items:
        a = await el.query_selector("a")
        if a:
            href = await a.get_attribute("href")
            if href:
                abs_url = _absolute(href, settings.amazon_base_url)
                if abs_url and "/stores/" in abs_url and abs_url not in sub_urls:
                    sub_urls.append(abs_url)

    # De-dup and cap
    sub_urls = list(dict.fromkeys(sub_urls))[:max_subpages]

    for url in sub_urls:
        if url in snap.pages_visited:
            continue
        try:
            await polite_goto(page, url, settings)
            snap.pages_visited.append(page.url)

            videos = await page.query_selector_all(", ".join(BRAND_STORE["videos"]))
            snap.video_count += len(videos)

            tiles = await page.query_selector_all(", ".join(BRAND_STORE["product_tiles"]))
            snap.product_tile_count += len(tiles)

            if not snap.about_us_text:
                about = _extract_about_section(await page.content())
                if about:
                    snap.about_us_text = about
                    snap.brand_story_present = True
        except Exception as exc:  # keep crawling even if one sub-page fails
            log.warning("brand_subpage_failed", url=url, error=str(exc))

    snap.page_count = len(snap.pages_visited)


def _absolute(href: str, base: str) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return urlparse.urljoin(base, href)


# Lightweight "About Us / Our Story" heuristic that doesn't require a fragile selector.
_ABOUT_KEYWORDS = (
    "about us",
    "our story",
    "our mission",
    "about the brand",
    "brand story",
    "from the brand",
    "who we are",
)


def _extract_about_section(html: str) -> str | None:
    """Search rendered HTML for an about-us block; return the first matching paragraph."""
    if not html:
        return None
    lowered = html.lower()
    for kw in _ABOUT_KEYWORDS:
        idx = lowered.find(kw)
        if idx == -1:
            continue
        # Grab a 2,000-char window around the keyword and strip tags roughly.
        window = html[max(0, idx - 200) : idx + 2000]
        # Cheap tag strip
        import re

        text = re.sub(r"<[^>]+>", " ", window)
        text = clean_text(text)
        if text and len(text) > 80:
            return text[:2000]
    return None


async def _first_element(page: Page, selectors: list[str]):
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            return el
    return None


async def write_brand_store_snapshot(
    *,
    org_id: str,
    audit_id: str,
    snapshot: BrandStoreSnapshot,
) -> None:
    payload = json.dumps(
        {
            "store_url": snapshot.store_url,
            "exists": snapshot.exists,
            "page_count": snapshot.page_count,
            "has_hero": snapshot.has_hero,
            "video_count": snapshot.video_count,
            "nav_depth": snapshot.nav_depth,
            "product_tile_count": snapshot.product_tile_count,
            "about_us_text": snapshot.about_us_text,
            "brand_story_present": snapshot.brand_story_present,
            "pages_visited": snapshot.pages_visited,
        }
    )

    async def _do(conn: asyncpg.Connection) -> None:
        await conn.execute(
            """
            INSERT INTO audit_brand_data (
                audit_id, org_id, brand_store_url, brand_store_json,
                brand_story_detected, video_count, asin_count
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            """,
            audit_id,
            org_id,
            snapshot.store_url,
            payload,
            snapshot.brand_story_present,
            snapshot.video_count,
            0,  # asin_count is written separately — brand store scrape doesn't count it
        )

    await with_tenant(org_id, _do)
