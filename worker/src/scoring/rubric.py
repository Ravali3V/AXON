"""100-point Brand Audit Tier 1 rubric — 5-section structure.

Sections and point allocations:
  Listing Quality      30 pts  — title, bullets, images, description, price consistency
  Ratings & Reviews    20 pts  — avg rating, volume, velocity, verified ratio
  Brand Presence       20 pts  — store exists, store quality, A+ coverage, brand story, registry
  Buy Box Health       15 pts  — ownership %, 3P seller risk
  Content Quality      15 pts  — BSR performance, video coverage, A+ depth, completeness

Grade thresholds:
  85-100  Thriving
  70-84   Growing
  55-69   Building
  40-54   Emerging
  0-39    Untapped
"""

from __future__ import annotations

from collections.abc import Callable
from statistics import mean, stdev

from .models import (
    AuditData,
    CriterionResult,
    Finding,
    AuditGradeResult,
)

# ============================================================================
# Section: Listing Quality (30 pts)
# ============================================================================


def score_title_quality(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Listing Quality", "Title Optimization", 8, "no ASINs scraped")
    good = [a for a in d.asins if a.title and 80 <= len(a.title) <= 200]
    ratio = len(good) / len(d.asins)
    earned = round(8 * ratio, 2)
    return CriterionResult(
        section="Listing Quality",
        criterion="Title Optimization",
        points_earned=earned,
        points_possible=8,
        status="scored",
        evidence={"asins_evaluated": len(d.asins), "well_formed_titles": len(good), "ratio": ratio},
    )


def score_bullets(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Listing Quality", "Bullet Points", 8, "no ASINs scraped")
    full = [a for a in d.asins if a.bullet_count >= 5]
    ratio = len(full) / len(d.asins)
    earned = round(8 * ratio, 2)
    return CriterionResult(
        section="Listing Quality",
        criterion="Bullet Points",
        points_earned=earned,
        points_possible=8,
        status="scored",
        evidence={"asins_with_5_bullets": len(full), "ratio": ratio},
    )


def score_images(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Listing Quality", "Images", 7, "no ASINs scraped")
    avg_images = mean([a.image_count for a in d.asins])
    if avg_images >= 7:
        earned = 7.0
    elif avg_images >= 5:
        earned = 5.5
    elif avg_images >= 3:
        earned = 3.5
    elif avg_images >= 1:
        earned = 1.5
    else:
        earned = 0.0
    return CriterionResult(
        section="Listing Quality",
        criterion="Product Images",
        points_earned=earned,
        points_possible=7,
        status="scored",
        evidence={"avg_images": round(avg_images, 2), "asins": len(d.asins)},
    )


def score_description(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Listing Quality", "Product Description", 4, "no ASINs scraped")
    with_desc = [a for a in d.asins if a.description and len(a.description) > 50]
    ratio = len(with_desc) / len(d.asins)
    earned = round(4 * ratio, 2)
    return CriterionResult(
        section="Listing Quality",
        criterion="Product Description",
        points_earned=earned,
        points_possible=4,
        status="scored",
        evidence={"asins_with_description": len(with_desc), "ratio": ratio},
    )


def score_price_consistency(d: AuditData) -> CriterionResult:
    prices = [a.price for a in d.asins if a.price is not None and a.price > 0]
    if len(prices) < 2:
        return _warning("Listing Quality", "Price Consistency", 3, "insufficient price data across ASINs")
    avg_price = mean(prices)
    if avg_price <= 0:
        return _warning("Listing Quality", "Price Consistency", 3, "zero average price")
    cv = stdev(prices) / avg_price
    if cv <= 0.10:
        earned = 3.0
    elif cv <= 0.25:
        earned = 2.0
    elif cv <= 0.40:
        earned = 1.0
    else:
        earned = 0.0
    return CriterionResult(
        section="Listing Quality",
        criterion="Price Consistency",
        points_earned=earned,
        points_possible=3,
        status="scored",
        evidence={"price_cv": round(cv, 3), "avg_price": round(avg_price, 2), "sample_count": len(prices)},
    )


# ============================================================================
# Section: Ratings & Reviews (20 pts)
# ============================================================================


def score_avg_rating(d: AuditData) -> CriterionResult:
    rated = [a.rating for a in d.asins if a.rating is not None]
    if not rated:
        return _warning("Ratings & Reviews", "Average Star Rating", 8, "no ratings captured")
    avg = mean(rated)
    if avg >= 4.5:
        earned = 8.0
    elif avg >= 4.2:
        earned = 6.5
    elif avg >= 4.0:
        earned = 5.0
    elif avg >= 3.5:
        earned = 3.0
    else:
        earned = 1.0
    return CriterionResult(
        section="Ratings & Reviews",
        criterion="Average Star Rating",
        points_earned=earned,
        points_possible=8,
        status="scored",
        evidence={"avg_rating": round(avg, 2), "asins_rated": len(rated)},
    )


def score_review_volume(d: AuditData) -> CriterionResult:
    counts = [a.review_count for a in d.asins if a.review_count is not None]
    if not counts:
        return _warning("Ratings & Reviews", "Review Volume", 6, "no review counts captured")
    avg_count = mean(counts)
    if avg_count >= 500:
        earned = 6.0
    elif avg_count >= 200:
        earned = 5.0
    elif avg_count >= 100:
        earned = 4.0
    elif avg_count >= 30:
        earned = 2.5
    elif avg_count >= 5:
        earned = 1.0
    else:
        earned = 0.0
    return CriterionResult(
        section="Ratings & Reviews",
        criterion="Review Volume",
        points_earned=earned,
        points_possible=6,
        status="scored",
        evidence={"avg_review_count": round(avg_count, 1), "asins_sampled": len(counts)},
    )


def score_review_velocity(d: AuditData) -> CriterionResult:
    """Proxy for recency: total review mass across catalog signals ongoing activity."""
    counts = [a.review_count for a in d.asins if a.review_count is not None]
    if not counts:
        return _warning("Ratings & Reviews", "Review Velocity", 4, "no review counts captured")
    total = sum(counts)
    avg = mean(counts)
    if total >= 10_000 or avg >= 300:
        earned = 4.0
    elif total >= 3_000 or avg >= 100:
        earned = 3.0
    elif total >= 500 or avg >= 25:
        earned = 2.0
    elif total > 0:
        earned = 1.0
    else:
        earned = 0.0
    return CriterionResult(
        section="Ratings & Reviews",
        criterion="Review Velocity",
        points_earned=earned,
        points_possible=4,
        status="scored",
        evidence={"total_reviews": total, "avg_per_asin": round(avg, 1)},
    )


def score_verified_ratio(d: AuditData) -> CriterionResult:
    if not d.reviews:
        return _warning("Ratings & Reviews", "Verified Purchase Ratio", 2, "no reviews sampled")
    verified = [r for r in d.reviews if r.verified]
    ratio = len(verified) / len(d.reviews)
    if ratio >= 0.8:
        earned = 2.0
    elif ratio >= 0.5:
        earned = 1.5
    elif ratio > 0:
        earned = 0.5
    else:
        earned = 0.0
    return CriterionResult(
        section="Ratings & Reviews",
        criterion="Verified Purchase Ratio",
        points_earned=earned,
        points_possible=2,
        status="scored",
        evidence={"verified_ratio": round(ratio, 3), "reviews_sampled": len(d.reviews)},
    )


# ============================================================================
# Section: Brand Presence (20 pts)
# ============================================================================


def score_store_exists(d: AuditData) -> CriterionResult:
    exists = d.brand_store.exists
    return CriterionResult(
        section="Brand Presence",
        criterion="Brand Store Exists",
        points_earned=5.0 if exists else 0.0,
        points_possible=5,
        status="scored",
        evidence={"store_url": d.brand_store.store_url},
    )


def score_store_quality(d: AuditData) -> CriterionResult:
    if not d.brand_store.exists:
        return CriterionResult(
            section="Brand Presence",
            criterion="Store Quality",
            points_earned=0.0,
            points_possible=5,
            status="scored",
            evidence={"reason": "no brand store detected"},
        )
    score = 0.0
    pages = d.brand_store.page_count
    nav = d.brand_store.nav_depth
    tiles = d.brand_store.product_tile_count
    hero = d.brand_store.has_hero

    if hero:
        score += 1.5
    if pages >= 3:
        score += 1.5
    elif pages >= 1:
        score += 0.5
    if nav >= 4:
        score += 1.0
    elif nav >= 2:
        score += 0.5
    if tiles >= 8:
        score += 1.0
    elif tiles >= 3:
        score += 0.5

    return CriterionResult(
        section="Brand Presence",
        criterion="Store Quality",
        points_earned=min(round(score, 2), 5.0),
        points_possible=5,
        status="scored",
        evidence={
            "page_count": pages, "nav_depth": nav,
            "product_tile_count": tiles, "has_hero": hero,
        },
    )


def score_aplus_coverage(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Brand Presence", "A+ Content Coverage", 5, "no ASINs scraped")
    with_aplus = [a for a in d.asins if a.has_aplus]
    ratio = len(with_aplus) / len(d.asins)
    earned = round(5 * ratio, 2)
    return CriterionResult(
        section="Brand Presence",
        criterion="A+ Content Coverage",
        points_earned=earned,
        points_possible=5,
        status="scored",
        evidence={"asins_with_aplus": len(with_aplus), "ratio": ratio},
    )


def score_brand_story(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Brand Presence", "Brand Story", 3, "no ASINs scraped")
    with_story = [a for a in d.asins if a.has_brand_story]
    store_story = d.brand_store.brand_story_present
    ratio = len(with_story) / len(d.asins)
    if ratio >= 0.6 or store_story:
        earned = 3.0
    elif ratio >= 0.2:
        earned = 2.0
    elif ratio > 0:
        earned = 1.0
    else:
        earned = 0.0
    return CriterionResult(
        section="Brand Presence",
        criterion="Brand Story",
        points_earned=earned,
        points_possible=3,
        status="scored",
        evidence={
            "asins_with_brand_story": len(with_story),
            "ratio": round(ratio, 3),
            "store_brand_story": store_story,
        },
    )


def score_brand_registry_signal(d: AuditData) -> CriterionResult:
    store = d.brand_store.exists
    any_aplus = any(a.has_aplus for a in d.asins)
    if store and any_aplus:
        earned = 2.0
        source = "brand_store + A+"
    elif store or any_aplus:
        earned = 1.5
        source = "brand_store" if store else "A+ content"
    else:
        earned = 0.0
        source = "not detected"
    return CriterionResult(
        section="Brand Presence",
        criterion="Brand Registry Signal",
        points_earned=earned,
        points_possible=2,
        status="scored",
        evidence={"inferred_from": source, "brand_store": store, "aplus_present": any_aplus},
    )


# ============================================================================
# Section: Buy Box Health (15 pts)
# ============================================================================


def score_buybox_ownership(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Buy Box Health", "Buy Box Ownership", 10, "no ASINs scraped")
    brand_words = {w for w in d.brand_name.lower().split() if len(w) >= 5}
    brand_lower = d.brand_name.lower().strip()

    def _is_brand_healthy(seller: str | None) -> bool:
        if not seller:
            return False
        sl = seller.lower()
        if brand_lower in sl:
            return True
        # Amazon.com / Amazon fulfilling = brand sells via FBA → brand controls inventory
        if "amazon" in sl:
            return True
        return bool(brand_words and any(w in sl for w in brand_words))

    matched = [a for a in d.asins if _is_brand_healthy(a.buybox_seller)]
    ratio = len(matched) / len(d.asins)
    if ratio >= 0.9:
        earned = 10.0
    elif ratio >= 0.7:
        earned = 8.0
    elif ratio >= 0.5:
        earned = 5.5
    elif ratio >= 0.25:
        earned = 3.0
    elif ratio > 0:
        earned = 1.5
    else:
        earned = 0.0
    return CriterionResult(
        section="Buy Box Health",
        criterion="Buy Box Ownership",
        points_earned=earned,
        points_possible=10,
        status="scored",
        evidence={
            "brand_owned_ratio": round(ratio, 3),
            "brand_owned_count": len(matched),
            "total_asins": len(d.asins),
        },
    )


def score_third_party_risk(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Buy Box Health", "3P Seller Risk", 5, "no ASINs scraped")
    brand_words = {w for w in d.brand_name.lower().split() if len(w) >= 5}
    brand_lower = d.brand_name.lower().strip()

    at_risk = []
    for a in d.asins:
        if not a.buybox_seller:
            continue
        sl = a.buybox_seller.lower()
        is_brand = brand_lower in sl or bool(brand_words and any(w in sl for w in brand_words))
        is_amazon = "amazon" in sl  # FBA or Amazon Retail — both are non-adversarial
        if not is_brand and not is_amazon:
            at_risk.append(a.asin)

    risk_ratio = len(at_risk) / len(d.asins)
    if risk_ratio == 0:
        earned = 5.0
    elif risk_ratio <= 0.1:
        earned = 4.0
    elif risk_ratio <= 0.3:
        earned = 3.0
    elif risk_ratio <= 0.5:
        earned = 1.5
    else:
        earned = 0.0
    return CriterionResult(
        section="Buy Box Health",
        criterion="3P Seller Risk",
        points_earned=earned,
        points_possible=5,
        status="scored",
        evidence={
            "at_risk_count": len(at_risk),
            "risk_ratio": round(risk_ratio, 3),
            "at_risk_asins": at_risk[:10],
        },
    )


# ============================================================================
# Section: Content Quality (15 pts)
# ============================================================================


def score_bsr_performance(d: AuditData) -> CriterionResult:
    ranked = [a.bsr for a in d.asins if a.bsr is not None]
    if not ranked:
        return _warning("Content Quality", "BSR Performance", 5, "no BSR data captured")
    avg = mean(ranked)
    if avg < 5_000:
        earned = 5.0
    elif avg < 20_000:
        earned = 4.0
    elif avg < 75_000:
        earned = 3.0
    elif avg < 200_000:
        earned = 2.0
    else:
        earned = 1.0
    return CriterionResult(
        section="Content Quality",
        criterion="BSR Performance",
        points_earned=earned,
        points_possible=5,
        status="scored",
        evidence={"avg_bsr": round(avg), "asins_with_bsr": len(ranked)},
    )


def score_video_coverage(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Content Quality", "Video Coverage", 5, "no ASINs scraped")
    with_video = [a for a in d.asins if a.has_video]
    ratio = len(with_video) / len(d.asins)
    if ratio >= 0.8:
        earned = 5.0
    elif ratio >= 0.5:
        earned = 4.0
    elif ratio >= 0.25:
        earned = 2.5
    elif ratio > 0:
        earned = 1.0
    else:
        earned = 0.0
    return CriterionResult(
        section="Content Quality",
        criterion="Video Coverage",
        points_earned=earned,
        points_possible=5,
        status="scored",
        evidence={"ratio_with_video": round(ratio, 3), "asins_with_video": len(with_video)},
    )


def score_aplus_depth(d: AuditData) -> CriterionResult:
    aplus_asins = [a for a in d.asins if a.has_aplus]
    if not aplus_asins:
        return CriterionResult(
            section="Content Quality",
            criterion="A+ Module Depth",
            points_earned=0.0,
            points_possible=3,
            status="scored",
            evidence={"reason": "no A+ content detected"},
        )
    avg_modules = mean([getattr(a, "aplus_module_count", 0) for a in aplus_asins])
    if avg_modules >= 6:
        earned = 3.0
    elif avg_modules >= 3:
        earned = 2.0
    elif avg_modules >= 1:
        earned = 1.0
    else:
        earned = 0.0
    return CriterionResult(
        section="Content Quality",
        criterion="A+ Module Depth",
        points_earned=earned,
        points_possible=3,
        status="scored",
        evidence={"avg_modules": round(avg_modules, 1), "aplus_asins": len(aplus_asins)},
    )


def score_enhanced_completeness(d: AuditData) -> CriterionResult:
    if not d.asins:
        return _warning("Content Quality", "Enhanced Content Completeness", 2, "no ASINs scraped")
    complete = [a for a in d.asins if a.has_aplus and a.has_brand_story and a.has_video]
    ratio = len(complete) / len(d.asins)
    if ratio >= 0.7:
        earned = 2.0
    elif ratio >= 0.3:
        earned = 1.0
    else:
        earned = 0.0
    return CriterionResult(
        section="Content Quality",
        criterion="Enhanced Content Completeness",
        points_earned=earned,
        points_possible=2,
        status="scored",
        evidence={"fully_enhanced_asins": len(complete), "ratio": round(ratio, 3)},
    )


# ============================================================================
# Runner
# ============================================================================

CRITERIA: list[Callable[[AuditData], CriterionResult]] = [
    # Listing Quality (30 pts)
    score_title_quality,
    score_bullets,
    score_images,
    score_description,
    score_price_consistency,
    # Ratings & Reviews (20 pts)
    score_avg_rating,
    score_review_volume,
    score_review_velocity,
    score_verified_ratio,
    # Brand Presence (20 pts)
    score_store_exists,
    score_store_quality,
    score_aplus_coverage,
    score_brand_story,
    score_brand_registry_signal,
    # Buy Box Health (15 pts)
    score_buybox_ownership,
    score_third_party_risk,
    # Content Quality (15 pts)
    score_bsr_performance,
    score_video_coverage,
    score_aplus_depth,
    score_enhanced_completeness,
]


def run_all(data: AuditData) -> list[CriterionResult]:
    return [fn(data) for fn in CRITERIA]


def compute_grade(criteria: list[CriterionResult]) -> AuditGradeResult:
    """Aggregate per-criterion results into totals + grade label.

    `na` and `warning` criteria with 0 earned are excluded from denominator so
    the final score is always on a 100-point scale.
    """
    scorable = [c for c in criteria if c.status != "na"]
    raw_possible = sum(c.points_possible for c in scorable)
    raw_earned = sum(c.points_earned for c in scorable)
    percentage = (raw_earned / raw_possible * 100) if raw_possible else 0.0

    scale = 100.0 / raw_possible if raw_possible > 0 else 1.0
    total_earned = round(raw_earned * scale, 1)
    total_possible = 100.0

    if percentage >= 85:
        grade = "Thriving"
    elif percentage >= 70:
        grade = "Growing"
    elif percentage >= 55:
        grade = "Building"
    elif percentage >= 40:
        grade = "Emerging"
    else:
        grade = "Untapped"

    findings = generate_rule_based_findings(criteria)

    return AuditGradeResult(
        total_earned=total_earned,
        total_possible=total_possible,
        percentage=round(percentage, 1),
        grade=grade,
        criteria=criteria,
        findings=findings,
    )


def generate_rule_based_findings(criteria: list[CriterionResult]) -> list[Finding]:
    findings: list[Finding] = []
    for c in criteria:
        if c.status == "na":
            continue
        if c.points_possible == 0:
            continue
        pct = c.points_earned / c.points_possible if c.points_possible else 0

        if pct >= 0.8 and c.status == "scored":
            findings.append(Finding(
                type="strength",
                section=c.section,
                text=f"{c.criterion}: {c.points_earned}/{c.points_possible} — well-executed.",
                priority=4,
            ))
        elif pct <= 0.3 and c.status == "scored":
            findings.append(Finding(
                type="weakness",
                section=c.section,
                text=(
                    f"{c.criterion}: {c.points_earned}/{c.points_possible}. "
                    "This is well below target — see recommendation below."
                ),
                priority=2,
            ))
            findings.append(Finding(
                type="recommendation",
                section=c.section,
                text=_recommendation_for(c),
                priority=2,
            ))
        elif c.status == "warning":
            findings.append(Finding(
                type="weakness",
                section=c.section,
                text=(
                    f"{c.criterion}: data unavailable "
                    f"({c.evidence.get('reason', 'see methodology')}). "
                    f"Scored 0/{c.points_possible} until resolved."
                ),
                priority=3,
            ))

    quick_wins = _pick_quick_wins(criteria)
    findings.extend(quick_wins)
    return findings


def _recommendation_for(c: CriterionResult) -> str:
    lookup = {
        "Title Optimization": "Revise titles to 80–200 chars including top keywords; avoid keyword stuffing.",
        "Bullet Points": "Use all 5 bullet points; lead each with a customer benefit backed by a product spec.",
        "Product Images": "Target 7 images per ASIN: hero + 3 lifestyle + 2 infographic + 1 size-comparison.",
        "Product Description": "Add a description block on every ASIN covering use cases and key differentiators.",
        "Price Consistency": "Review pricing strategy — high variance signals reseller interference or inconsistent positioning.",
        "Average Star Rating": "Launch a post-purchase follow-up via Amazon's Request-a-Review button to boost quality feedback.",
        "Review Volume": "Enroll in Amazon Vine for new ASINs to build initial review volume.",
        "Review Velocity": "Launch sponsored campaigns on top ASINs to drive traffic and organic review velocity.",
        "Verified Purchase Ratio": "Focus on organic follow-ups; avoid any incentivized-review activity.",
        "Brand Store Exists": "Build a Brand Store — it's free via Brand Registry and materially lifts conversion.",
        "Store Quality": "Expand your Brand Store: add a hero image, sub-pages per product category, and a navigation menu.",
        "A+ Content Coverage": "Add A+ Enhanced Brand Content to every ASIN — included with Brand Registry at no extra cost.",
        "Brand Story": "Enable the 'From the Brand' module on every listing — it's free and increases purchase intent.",
        "Brand Registry Signal": "Enroll in Amazon Brand Registry to unlock A+, Brand Store, and buy box protection tools.",
        "Buy Box Ownership": "Identify 3P resellers via test-buys and escalate through Brand Registry enforcement tools.",
        "3P Seller Risk": "Implement a MAP (Minimum Advertised Price) policy and enforce it via Brand Registry.",
        "BSR Performance": "Invest in sponsored keyword campaigns on your 3 top ASINs to improve organic rank and BSR.",
        "Video Coverage": "Add a 30–60 second product demo video to your top-selling ASINs — video listings convert up to 80% better.",
        "A+ Module Depth": "Expand A+ content to include comparison charts, lifestyle imagery, and brand story modules.",
        "Enhanced Content Completeness": "Aim for every ASIN to have A+, Brand Story, and Video — this full suite maximises conversion.",
    }
    return lookup.get(
        c.criterion,
        f"{c.criterion} scored below target. Review the evidence in the Detailed Scores tab and plan an action.",
    )


def _pick_quick_wins(criteria: list[CriterionResult]) -> list[Finding]:
    candidates = [
        ("Brand Story", "Enable the 'From the Brand' module (free with Brand Registry). Lifts PDP engagement immediately."),
        ("Bullet Points", "Fill all 5 bullets on every ASIN — Amazon penalises incomplete listings in search ranking."),
        ("Product Images", "Add at least 7 images per ASIN, including an infographic and a lifestyle shot."),
        ("Video Coverage", "Upload a 30-second product demo video to your top-3 ASINs."),
        ("A+ Content Coverage", "Add A+ Content to every ASIN — included in Brand Registry at no cost."),
        ("Brand Store Exists", "Launch a Brand Store — free, permanent, and drives all future campaign traffic."),
    ]
    picked: list[Finding] = []
    criteria_by_name = {c.criterion: c for c in criteria}
    for name, text in candidates:
        c = criteria_by_name.get(name)
        if c and c.status == "scored" and c.points_possible:
            if c.points_earned / c.points_possible < 0.6:
                picked.append(Finding(type="quick_win", section=c.section, text=text, priority=1))
                if len(picked) >= 5:
                    break
    return picked


# ============================================================================
# Helpers
# ============================================================================


def _warning(section: str, criterion: str, possible: int, reason: str) -> CriterionResult:
    return CriterionResult(
        section=section,
        criterion=criterion,
        points_earned=0.0,
        points_possible=possible,
        status="warning",
        evidence={"reason": reason},
    )
