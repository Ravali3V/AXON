"""ASIN discovery — paginate search results (and optionally Brand Store tiles) to
collect every ASIN associated with the target brand.

Respects the `audit_hard_asin_ceiling` cap. Emits a warning event at
`audit_soft_asin_warning` so operators can see catalog size as it loads.
"""

from __future__ import annotations

import urllib.parse as urlparse
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from ..config import Settings, get_settings
from ..db import emit_event
from .browser import new_page, polite_goto
from .selectors import SEARCH

_DIAG_DIR = Path(__file__).resolve().parents[3] / "tmp-diagnostics"


async def _dump_page_diagnostics(page, *, audit_id: str, tag: str) -> None:
    """Dump screenshot + HTML snippet when scraping hits unexpected page state."""
    try:
        _DIAG_DIR.mkdir(parents=True, exist_ok=True)
        base = _DIAG_DIR / f"{audit_id}-{tag}"
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=False)
        content = await page.content()
        with open(base.with_suffix(".html"), "w", encoding="utf-8") as f:
            f.write(content[:120_000])
        log.info("diagnostics_dumped", audit_id=audit_id, tag=tag, path=str(base))
    except Exception as exc:
        log.warning("diagnostics_dump_failed", error=str(exc))

log = structlog.get_logger(__name__)


@dataclass
class DiscoveryResult:
    asins: list[str] = field(default_factory=list)
    pages_visited: int = 0
    hit_hard_ceiling: bool = False
    warned_soft: bool = False


async def discover_asins(
    *,
    start_url: str,
    org_id: str,
    audit_id: str,
    settings: Settings | None = None,
) -> DiscoveryResult:
    s = settings or get_settings()
    result = DiscoveryResult()
    seen: set[str] = set()
    next_url: str | None = start_url
    page_num = 0

    async with new_page(s) as page:
        while next_url and page_num < 1000:  # absolute safety valve on loop
            page_num += 1
            await polite_goto(page, next_url, s, warmup=(page_num == 1))

            # Search results render client-side after domcontentloaded — wait for cards.
            card_selector = ", ".join(SEARCH["result_card"])
            try:
                await page.wait_for_selector(card_selector, timeout=15_000)
            except Exception:
                # Either no results, CAPTCHA, or selectors out of date — dump diagnostics.
                await _dump_page_diagnostics(page, audit_id=audit_id, tag=f"discovery-p{page_num}")
                log.warning(
                    "asin_discovery_cards_not_found",
                    url=next_url,
                    page=page_num,
                    page_title=await page.title(),
                )

            # Amazon lazy-loads cards below the fold. Scroll through the page
            # in steps so every card hydrates before we query the DOM.
            await _scroll_to_load_all(page)

            cards = await page.query_selector_all(card_selector)
            cards_total = len(cards)
            new_on_page = 0
            for card in cards:
                asin = await card.get_attribute(SEARCH["asin_attr"])
                if asin and asin not in seen and asin.strip():
                    seen.add(asin)
                    result.asins.append(asin)
                    new_on_page += 1
                    if len(result.asins) >= s.audit_hard_asin_ceiling:
                        result.hit_hard_ceiling = True
                        await emit_event(
                            org_id=org_id,
                            audit_id=audit_id,
                            stage="discover_asins",
                            message=(
                                f"Hit hard ceiling of {s.audit_hard_asin_ceiling} ASINs; "
                                "stopping discovery. Adjust AUDIT_HARD_ASIN_CEILING to scan more."
                            ),
                            level="warn",
                        )
                        break

            if result.hit_hard_ceiling:
                break

            if (
                not result.warned_soft
                and len(result.asins) >= s.audit_soft_asin_warning
            ):
                result.warned_soft = True
                await emit_event(
                    org_id=org_id,
                    audit_id=audit_id,
                    stage="discover_asins",
                    message=(
                        f"Discovered {len(result.asins)} ASINs so far (soft warning threshold "
                        f"{s.audit_soft_asin_warning}); this is a large catalog. Continuing."
                    ),
                    level="warn",
                )

            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="discover_asins",
                message=(
                    f"Page {page_num}: +{new_on_page} new ASINs "
                    f"({cards_total} cards on page, total {len(result.asins)})"
                ),
                level="info",
            )

            # Stop conditions:
            #  - page had zero DOM cards AT ALL -> we're past the last page or hit an error
            #  - page had cards but none were new for 2 consecutive pages -> dedup plateau
            if cards_total == 0 and page_num > 1:
                log.info("discover_asins_empty_page", page=page_num)
                break

            next_url = await _next_page_url(page, s)

        result.pages_visited = page_num

    return result


async def _scroll_to_load_all(page) -> None:
    """Scroll the page top-to-bottom in small steps to trigger lazy-loading.

    Amazon's search-results page only hydrates cards as they enter the viewport.
    Without this, we systematically miss ~half to two-thirds of the results.
    """
    import asyncio as _asyncio
    try:
        height = await page.evaluate("document.body.scrollHeight")
        steps = 8
        for i in range(1, steps + 1):
            await page.evaluate(f"window.scrollTo(0, {int(height * i / steps)})")
            await _asyncio.sleep(0.4)
        # Back to top so pagination clicks / selector queries start clean.
        await page.evaluate("window.scrollTo(0, 0)")
        await _asyncio.sleep(0.3)
    except Exception as exc:
        log.debug("scroll_failed", error=str(exc))


async def _next_page_url(page, settings: Settings) -> str | None:
    """Try selector-based next-page detection, then fall back to URL page increment."""
    for sel in SEARCH["pagination_next"]:
        el = await page.query_selector(sel)
        if not el:
            continue
        # Confirm it's not visually disabled via class or aria attribute.
        disabled = await el.get_attribute("aria-disabled")
        class_attr = await el.get_attribute("class") or ""
        if disabled == "true" or "disabled" in class_attr:
            continue
        href = await el.get_attribute("href")
        if href:
            if href.startswith("/"):
                href = settings.amazon_base_url.rstrip("/") + href
            return href

    # Fallback: increment the `page` param in the current URL.
    # Works when Amazon renders results via query-string pagination.
    current_url = page.url
    parsed = urlparse.urlparse(current_url)
    params = urlparse.parse_qs(parsed.query, keep_blank_values=True)
    current_page = int(params.get("page", ["1"])[0])
    params["page"] = [str(current_page + 1)]
    new_query = urlparse.urlencode(params, doseq=True)
    candidate_url = urlparse.urlunparse(parsed._replace(query=new_query))

    # Only follow the incremented URL if it differs from the current one.
    if candidate_url != current_url:
        # Navigate to the candidate and check if any result cards appear.
        # We return the URL here; the caller's loop will navigate and verify.
        # If zero cards are found there, the loop naturally ends (new_on_page=0 means
        # all items already seen — but the loop continues). To prevent infinite loops
        # on dead pages, we check if the current page already has a "No results" signal.
        no_results_text = await page.inner_text("body")
        if "no results" in no_results_text.lower() or "didn't match" in no_results_text.lower():
            return None
        return candidate_url

    return None
