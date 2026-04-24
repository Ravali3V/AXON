"""Data shapes passed between the scoring engine's layers.

`AuditData` is the input — everything scraped from a brand. `CriterionResult` is what
each scoring rule produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ScoreStatus = Literal["scored", "na", "warning"]


@dataclass
class AsinDatum:
    asin: str
    title: str | None = None
    bullet_count: int = 0
    description: str | None = None
    image_count: int = 0
    aplus_module_count: int = 0
    has_aplus: bool = False
    has_brand_story: bool = False
    has_video: bool = False
    rating: float | None = None
    review_count: int | None = None
    bsr: int | None = None
    bsr_category: str | None = None
    buybox_seller: str | None = None
    variation_parent_asin: str | None = None
    price: float | None = None


@dataclass
class ReviewDatum:
    asin: str
    rating: int | None
    verified: bool
    body: str | None


@dataclass
class BrandStoreDatum:
    exists: bool = False
    store_url: str | None = None
    page_count: int = 0
    video_count: int = 0
    nav_depth: int = 0
    about_us_text: str | None = None
    brand_story_present: bool = False
    product_tile_count: int = 0
    has_hero: bool = False


@dataclass
class AuditData:
    brand_name: str
    asins: list[AsinDatum]
    reviews: list[ReviewDatum]
    brand_store: BrandStoreDatum


@dataclass
class CriterionResult:
    section: str
    criterion: str
    points_earned: float
    points_possible: float
    status: ScoreStatus
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    type: Literal["strength", "weakness", "recommendation", "quick_win"]
    section: str
    text: str
    priority: int  # 1 = highest, 5 = lowest
    source: Literal["rule", "llm"] = "rule"


@dataclass
class AuditGradeResult:
    total_earned: float
    total_possible: float
    percentage: float
    grade: str  # Thriving / Growing / Building / Emerging / Untapped
    criteria: list[CriterionResult]
    findings: list[Finding]
