"""Brand resolution — turn a user-entered brand name into canonical search + store URLs.

Strategy:
  1. Sanitize the brand name (strip punctuation, normalize whitespace).
  2. Hit /s?k=<brand>. Look for:
     - Brand store banner ("Shop X Store >") at top of results
     - Brand facet link in left sidebar (Brands filter checkbox)
  3. If no facet found, construct a manual brand-filter URL via `&rh=p_89:<brand>`
     — Amazon accepts this format for most brands.
  4. Return the best URLs we could find.
"""

from __future__ import annotations

import re
import urllib.parse as urlparse
from dataclasses import dataclass

import structlog

from ..config import Settings, get_settings
from .browser import new_page, polite_goto, first_match_attr
from .selectors import SEARCH

log = structlog.get_logger(__name__)


@dataclass
class BrandResolution:
    brand_name_query: str
    search_url: str
    brand_store_url: str | None
    filtered_search_url: str | None


def sanitize_brand_name(raw: str) -> str:
    """Normalize user-entered brand name: trim, drop trailing punctuation, collapse spaces."""
    if not raw:
        return ""
    # Strip surrounding whitespace and common trailing punctuation (.,;:!?)
    cleaned = raw.strip().rstrip(".,;:!? ")
    # Collapse internal whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


async def resolve_brand(brand_name: str, settings: Settings | None = None) -> BrandResolution:
    s = settings or get_settings()
    base = s.amazon_base_url

    clean_name = sanitize_brand_name(brand_name)
    if clean_name != brand_name:
        log.info("brand_name_sanitized", original=brand_name, cleaned=clean_name)

    search_url = f"{base}/s?{urlparse.urlencode({'k': clean_name})}"

    async with new_page(s) as page:
        await polite_goto(page, search_url, s, warmup=True)

        # Wait for results layout to render — Amazon hydrates after domcontentloaded.
        try:
            await page.wait_for_selector(
                'div[data-asin], #search, .s-main-slot', timeout=15_000
            )
        except Exception:
            await _dump_diag(page, clean_name)
            log.warning(
                "brand_resolver_search_not_loaded",
                url=search_url,
                page_title=await page.title(),
            )

        brand_store_url = await _find_brand_store_link(page, base)
        filtered_url    = await _find_brand_facet_url(page, base, clean_name)

    # Fallback 1: construct manual brand-filter URL if no facet found.
    if not filtered_url:
        filtered_url = _construct_brand_filter_url(base, clean_name)
        log.info("brand_filter_url_constructed", url=filtered_url)

    return BrandResolution(
        brand_name_query=clean_name,
        search_url=search_url,
        brand_store_url=brand_store_url,
        filtered_search_url=filtered_url,
    )


def _construct_brand_filter_url(base: str, brand_name: str) -> str:
    """Build `/s?k=<brand>&rh=p_89:<brand>` — Amazon's brand refinement URL pattern.

    Works for the majority of brands where the facet value == brand name.
    Amazon is case-insensitive on p_89 values.
    """
    # Amazon's p_89 filter takes the brand display name URL-encoded.
    rh_value = f"p_89:{brand_name}"
    query = urlparse.urlencode({"k": brand_name, "rh": rh_value})
    return f"{base}/s?{query}"


async def _find_brand_store_link(page, base: str) -> str | None:
    """Prefer banner-specific anchors; filter out the per-ASIN byline variants."""
    # Collect ALL store links first, then pick the one most likely to be the
    # brand banner (shortest path, no /page/ fragment pointing at an ASIN tile).
    elements = await page.query_selector_all(", ".join(SEARCH["store_link"]))
    candidates: list[str] = []
    for el in elements:
        href = await el.get_attribute("href")
        if not href:
            continue
        if href.startswith("/"):
            href = base.rstrip("/") + href
        if "/stores/" not in href:
            continue
        # Drop duplicates
        if href in candidates:
            continue
        candidates.append(href)

    if not candidates:
        return None

    # Pick the shortest URL — banner links are typically `/stores/<brand>/page/<uuid>`
    # while byline links can include tracking params that bloat the URL.
    candidates.sort(key=len)
    log.info("brand_store_candidates", count=len(candidates), chosen=candidates[0])
    return candidates[0]


async def _find_brand_facet_url(page, base: str, brand_name: str) -> str | None:
    links = await page.query_selector_all(", ".join(SEARCH["brand_facet"]))
    target = brand_name.strip().lower()
    # Build a set of tokens we're willing to accept as a match
    target_tokens = {t for t in target.split() if len(t) >= 3}

    for link in links:
        text = (await link.text_content() or "").strip().lower()
        if not text:
            continue
        # Exact / containment match, OR any 3+ letter token overlap with target
        if (
            text == target
            or target in text
            or text in target
            or bool(target_tokens & {t for t in text.split() if len(t) >= 3})
        ):
            href = await link.get_attribute("href")
            if href:
                if href.startswith("/"):
                    href = base.rstrip("/") + href
                return href
    return None


async def _dump_diag(page, brand_name: str) -> None:
    try:
        from pathlib import Path
        safe = re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-") or "brand"
        diag_dir = Path(__file__).resolve().parents[3] / "tmp-diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(diag_dir / f"resolver-{safe}.png"))
        with open(diag_dir / f"resolver-{safe}.html", "w", encoding="utf-8") as f:
            f.write((await page.content())[:120_000])
    except Exception:
        pass
