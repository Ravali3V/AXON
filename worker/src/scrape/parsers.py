"""Pure text parsers — turn raw scraped strings into structured values.

Kept separate from the Playwright scraping so we can unit-test the regex logic without
a browser. These functions are total — they always return a best-guess value or None,
never raise.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# e.g. "$24.99" or "£12.50" or "€9,99"
_PRICE_RE = re.compile(r"[\$£€]\s?([0-9]+(?:[.,][0-9]{2})?)")
# e.g. "4.3 out of 5 stars"
_RATING_RE = re.compile(r"([0-9](?:\.[0-9])?)\s*out\s*of\s*5", re.IGNORECASE)
# e.g. "1,234 ratings" / "3 ratings"
_REVIEW_COUNT_RE = re.compile(r"([0-9][0-9,]*)\s*(?:global\s*)?(?:ratings|reviews)", re.IGNORECASE)
# e.g. "#1,234 in Electronics" / "#5 in Kitchen & Dining (See Top 100 in ...)"
_BSR_RE = re.compile(r"#\s*([0-9][0-9,]*)\s+in\s+([^\n(]+)", re.IGNORECASE)


def parse_price(text: str | None) -> Decimal | None:
    """Extract a numeric price from a scraped string. Returns None if no match."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        # Some Amazon pages show price as "24" + "." + "99" in spans — try a plain number.
        m2 = re.search(r"([0-9]+\.[0-9]{2})", text)
        if not m2:
            return None
        raw = m2.group(1)
    else:
        raw = m.group(1).replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse_rating(text: str | None) -> float | None:
    """Extract 4.3 from 'Rated 4.3 out of 5 stars'."""
    if not text:
        return None
    m = _RATING_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parse_review_count(text: str | None) -> int | None:
    """Extract 1234 from '1,234 global ratings'."""
    if not text:
        return None
    m = _REVIEW_COUNT_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_bsr(text: str | None) -> tuple[int | None, str | None]:
    """
    Extract (rank, category) from BSR text blob.

    Amazon's Best Sellers Rank can list multiple categories. We return the PRIMARY
    (smallest / first) one — usually the top-level category.

    Example input:
        "Best Sellers Rank: #123 in Electronics (See Top 100 in Electronics) #4 in USB Hubs"
    Returns: (123, "Electronics")
    """
    if not text:
        return None, None
    matches = list(_BSR_RE.finditer(text))
    if not matches:
        return None, None
    m = matches[0]
    try:
        rank = int(m.group(1).replace(",", ""))
    except ValueError:
        return None, None
    category = m.group(2).strip(" ·•-—")
    category = re.sub(r"\s+", " ", category)
    return rank, category


def clean_text(text: str | None) -> str | None:
    """Normalize whitespace and strip. Returns None for empty results."""
    if not text:
        return None
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed or None
