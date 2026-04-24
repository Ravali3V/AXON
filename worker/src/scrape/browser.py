"""Playwright browser context factory with stealth + proxy rotation.

Responsibilities:
  - Create a Playwright context configured with a rotating User-Agent and optional
    residential proxy (from env).
  - Apply playwright-stealth to evade navigator.webdriver + canvas fingerprinting.
  - Detect Amazon's robot-check page and signal the caller to rotate proxies.

Usage:
    async with page_from_pool(settings) as page:
        await page.goto(url)
        ...
"""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import AsyncIterator

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth  # type: ignore[import-untyped]

_stealth = Stealth()

from ..config import Settings, get_settings
from .selectors import PDP

log = structlog.get_logger(__name__)

# Audit-scoped context variable. When set, all `new_page()` calls within the
# audit reuse ONE browser context so Amazon sees a continuous browsing session
# (persistent cookies, history, referer chain) instead of N fresh bots.
_current_audit_id: ContextVar[str | None] = ContextVar("current_audit_id", default=None)


@dataclass
class CaptchaDetected(Exception):
    url: str

    def __str__(self) -> str:  # pragma: no cover
        return f"Amazon robot-check page detected at {self.url}"


class BrowserPool:
    """Lazily-initialized singleton Playwright instance shared across audits."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()
        # audit_id -> single long-lived BrowserContext for that audit
        self._audit_contexts: dict[str, BrowserContext] = {}
        self._ctx_lock = asyncio.Lock()

    async def _ensure_browser(self) -> Browser:
        if self._browser is not None:
            return self._browser
        async with self._lock:
            if self._browser is None:
                self._playwright = await async_playwright().start()
                settings = get_settings()
                self._browser = await self._playwright.chromium.launch(
                    headless=settings.playwright_headless,
                )
        assert self._browser is not None
        return self._browser

    async def new_context(self, settings: Settings) -> BrowserContext:
        browser = await self._ensure_browser()
        user_agent = random.choice(settings.user_agents)
        # Randomise viewport slightly so every context has a unique fingerprint.
        width  = random.choice([1366, 1440, 1536, 1920])
        height = random.choice([768,  900,  864,  1080])
        context_args: dict = {
            "user_agent": user_agent,
            "viewport": {"width": width, "height": height},
            "screen":   {"width": width, "height": height},
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "light",
            # Pin geolocation to New York so Amazon treats us as US-based.
            "geolocation": {"latitude": 40.7128, "longitude": -74.0060},
            "permissions": ["geolocation"],
            "extra_http_headers": {
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        }
        if settings.has_proxy:
            context_args["proxy"] = {
                "server": f"http://{settings.proxy_endpoint}",
                "username": settings.proxy_username,
                "password": settings.proxy_password,
            }
        ctx = await browser.new_context(**context_args)
        # Pre-seed Amazon US locale/currency cookies before any navigation.
        await ctx.add_cookies([
            {"name": "i18n-prefs",  "value": "USD",   "domain": ".amazon.com", "path": "/"},
            {"name": "lc-main",     "value": "en_US", "domain": ".amazon.com", "path": "/"},
            {"name": "sp-cdn",      "value": '"L5Z9:US"', "domain": ".amazon.com", "path": "/"},
        ])
        return ctx

    async def context_for_audit(self, audit_id: str, settings: Settings) -> BrowserContext:
        """Return the audit's long-lived context, creating it on first call."""
        async with self._ctx_lock:
            ctx = self._audit_contexts.get(audit_id)
            if ctx is None:
                ctx = await self.new_context(settings)
                self._audit_contexts[audit_id] = ctx
                log.info("audit_context_created", audit_id=audit_id)
            return ctx

    async def close_audit(self, audit_id: str) -> None:
        async with self._ctx_lock:
            ctx = self._audit_contexts.pop(audit_id, None)
        if ctx is not None:
            try:
                await ctx.close()
            except Exception:
                pass
            log.info("audit_context_closed", audit_id=audit_id)

    async def close(self) -> None:
        for audit_id in list(self._audit_contexts.keys()):
            await self.close_audit(audit_id)
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


# Module-level singleton
browser_pool = BrowserPool()


@asynccontextmanager
async def audit_session(audit_id: str):
    """Scope an audit — all `new_page()` calls inside will reuse ONE context.

    This is the key to no-proxy scraping: Amazon sees a single coherent
    browsing session (cookies, history, referers) instead of N fresh bots.
    """
    token = _current_audit_id.set(audit_id)
    try:
        yield
    finally:
        await browser_pool.close_audit(audit_id)
        _current_audit_id.reset(token)


@asynccontextmanager
async def new_page(settings: Settings | None = None) -> AsyncIterator[Page]:
    """Yield a Playwright page with stealth patches applied.

    Inside an `audit_session(...)` block: opens a TAB in the audit's shared
    context (cookies persist across calls). Outside: creates a fresh context
    and closes it on exit (legacy standalone behaviour).
    """
    s = settings or get_settings()
    audit_id = _current_audit_id.get()

    if audit_id is not None:
        ctx = await browser_pool.context_for_audit(audit_id, s)
        page = await ctx.new_page()
        page.set_default_navigation_timeout(s.playwright_navigation_timeout_ms)
        await _stealth.apply_stealth_async(page)
        try:
            yield page
        finally:
            try:
                await page.close()  # close the tab; keep the context alive
            except Exception:
                pass
    else:
        ctx = await browser_pool.new_context(s)
        try:
            page = await ctx.new_page()
            page.set_default_navigation_timeout(s.playwright_navigation_timeout_ms)
            await _stealth.apply_stealth_async(page)
            yield page
        finally:
            await ctx.close()


async def polite_goto(
    page: Page,
    url: str,
    settings: Settings | None = None,
    *,
    warmup: bool = False,
    captcha_retries: int = 2,
) -> None:
    """`page.goto` with optional homepage warmup, CAPTCHA detection, and randomized delay.

    warmup=True navigates to the Amazon homepage first so the session has
    cookies and looks like a real user before hitting a search/product URL.

    On CAPTCHA: sleeps `scrape_captcha_cooldown_s * 2^attempt` seconds and
    retries up to `captcha_retries` times — suitable for single-IP no-proxy
    mode where Amazon rate-limits transiently.
    """
    s = settings or get_settings()
    if warmup:
        try:
            await page.goto(s.amazon_base_url, wait_until="domcontentloaded")
            await _set_us_delivery_zip(page)
            await asyncio.sleep(random.uniform(2.5, 5.0))
        except Exception:
            pass  # warmup failure is non-fatal; proceed to real URL

    last_exc: CaptchaDetected | None = None
    for attempt in range(captcha_retries + 1):
        await page.goto(url, wait_until="domcontentloaded")
        try:
            _check_for_block(page, url)
            break  # no block — success
        except CaptchaDetected as exc:
            last_exc = exc
            if attempt >= captcha_retries:
                raise
            cooldown = s.scrape_captcha_cooldown_s * (2 ** attempt)
            log.warning(
                "captcha_cooldown_retry",
                url=url, attempt=attempt + 1, cooldown_s=cooldown,
            )
            await asyncio.sleep(cooldown)
            # Re-warmup after cooldown so we have fresh session context.
            try:
                await page.goto(s.amazon_base_url, wait_until="domcontentloaded")
                await asyncio.sleep(random.uniform(3.0, 6.0))
            except Exception:
                pass
    if last_exc is None:
        pass  # no-op; the success path already broke out of loop

    # Polite delay so we don't hammer Amazon even when every request succeeds.
    delay_ms = random.uniform(s.scrape_min_delay_ms, s.scrape_max_delay_ms)
    await asyncio.sleep(delay_ms / 1000)


async def _check_for_block(page: Page, url: str) -> None:
    """Raise CaptchaDetected if the page looks like an Amazon block/error page.

    Checks URL redirects to /errors/, title phrases, and short body content
    containing block phrases (full-content pages with the word "captcha" in
    a review for example should NOT trigger this).
    """
    try:
        title = (await page.title()).lower()
    except Exception:
        title = ""
    try:
        body = (await page.content()).lower()
    except Exception:
        body = ""
    block_phrases = (
        "captcha", "not a robot", "unusual traffic",
        "sorry, we just need", "to discuss automated access",
        "enter the characters you see below",
    )
    is_block_url = "/errors/" in page.url.lower() or "/captcha" in page.url.lower()
    is_block_title = any(p in title for p in ("robot check", "sorry", "page not found"))
    is_block_body = any(p in body for p in block_phrases)
    if is_block_url or is_block_title or (is_block_body and len(body) < 50_000):
        log.warning(
            "captcha_detected",
            url=url, final_url=page.url, title=title, body_len=len(body),
        )
        raise CaptchaDetected(url=url)


async def _set_us_delivery_zip(page: Page, zip_code: str = "10001") -> None:
    """Force Amazon delivery to a US ZIP via the glow address-change endpoint.

    Two-step:
      1. Extract the CSRF token from the homepage (Amazon embeds it in window.csrfToken).
      2. POST it to the glow endpoint with the desired zip.

    On success, Amazon flips the session to "Deliver to New York 10001" and
    the search results now reflect US pricing/availability.
    """
    try:
        # Step 1: grab CSRF token the page already has.
        csrf_token = await page.evaluate(
            """
            () => {
              // Modern (SPA): window.CardJson or global CSRF carriers
              const direct = (window.csrfToken || window.CSRF_TOKEN || "");
              if (direct) return direct;
              // Fallback: parse inline <script> blocks
              const re = /CSRF[-_]?Token"?\\s*[:=]\\s*"([^"]+)"/i;
              for (const s of document.scripts) {
                const m = re.exec(s.textContent || "");
                if (m) return m[1];
              }
              return "";
            }
            """
        )
        headers = {"x-requested-with": "XMLHttpRequest", "anti-csrftoken-a2z": csrf_token or "1"}
        resp = await page.request.post(
            "https://www.amazon.com/portal-migration/hz/glow/address-change",
            data={
                "locationType": "LOCATION_INPUT",
                "zipCode": zip_code,
                "storeContext": "generic",
                "deviceType": "desktop",
                "pageType": "Gateway",
                "actionSource": "glow",
            },
            headers=headers,
            timeout=10_000,
        )
        body = await resp.text()
        ok = resp.status == 200 and ('"isValidAddress":1' in body or zip_code in body)
        log.info(
            "us_zip_set_attempt",
            status=resp.status, zip=zip_code, ok=ok,
            csrf_len=len(csrf_token or ""),
            body_snippet=body[:160],
        )
        # Reload the homepage so the glow banner reflects the new zip.
        if ok:
            await page.reload(wait_until="domcontentloaded")
            deliver_to = await page.evaluate(
                "document.querySelector('#glow-ingress-block')?.innerText || ''"
            )
            log.info("us_zip_deliver_to_after", text=deliver_to.strip()[:120])
    except Exception as exc:
        log.warning("us_zip_set_failed", error=str(exc))


async def first_match_text(page: Page, selectors: list[str]) -> str | None:
    """Return the trimmed text of the first matching selector, or None."""
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            text = await el.text_content()
            if text and text.strip():
                return text.strip()
    return None


async def first_match_attr(page: Page, selectors: list[str], attr: str) -> str | None:
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            val = await el.get_attribute(attr)
            if val:
                return val.strip()
    return None


async def all_matches(page: Page, selectors: list[str]):
    """Return list of element handles from the first selector that yields any match."""
    for sel in selectors:
        els = await page.query_selector_all(sel)
        if els:
            return els
    return []
