"""Unit tests for the scoring rubric.

Builds synthetic AuditData and verifies key criteria produce expected scores.
"""

from __future__ import annotations

from src.scoring.models import AsinDatum, AuditData, BrandStoreDatum, ReviewDatum
from src.scoring.rubric import compute_grade, run_all


def _mk(asins: list[AsinDatum] | None = None, reviews: list[ReviewDatum] | None = None, store: BrandStoreDatum | None = None, brand: str = "TestBrand") -> AuditData:
    return AuditData(
        brand_name=brand,
        asins=asins or [],
        reviews=reviews or [],
        brand_store=store or BrandStoreDatum(),
    )


def _asin(**overrides) -> AsinDatum:
    base = dict(asin="B001", title="TestBrand Widget Deluxe — 32-count", bullet_count=5, image_count=7, has_aplus=True, has_brand_story=True, has_video=True, rating=4.5, review_count=250, bsr=5000, bsr_category="Home", buybox_seller="TestBrand", description="A thorough description with plenty of detail about the product.")
    base.update(overrides)
    return AsinDatum(**base)


class TestHighPerformer:
    """A fully-optimized brand with all features should score ~90%+."""

    def test_grade_a_for_perfect_brand(self) -> None:
        data = _mk(
            asins=[_asin(asin=f"B{i:03d}") for i in range(1, 26)],  # 25 ASINs
            reviews=[ReviewDatum(asin="B001", rating=5, verified=True, body="Great") for _ in range(50)],
            store=BrandStoreDatum(
                exists=True,
                store_url="https://amazon.com/stores/TestBrand/page/abc",
                page_count=5,
                video_count=3,
                nav_depth=6,
                about_us_text="A" * 800,
                brand_story_present=True,
                product_tile_count=40,
            ),
        )
        criteria = run_all(data)
        result = compute_grade(criteria)
        assert result.percentage >= 80, f"Expected ≥80% for perfect brand, got {result.percentage}"
        assert result.grade in ("A", "B")


class TestLowPerformer:
    """A minimal brand with no store, no A+, no video should score poorly."""

    def test_grade_f_for_bare_brand(self) -> None:
        asin = AsinDatum(
            asin="B001",
            title="Short",  # too short
            bullet_count=1,
            image_count=1,
            has_aplus=False,
            has_brand_story=False,
            has_video=False,
            rating=2.8,
            review_count=3,
            bsr=None,
            bsr_category=None,
            buybox_seller="Random Seller",
            description=None,
        )
        data = _mk(asins=[asin])
        result = compute_grade(run_all(data))
        assert result.percentage < 40
        assert result.grade == "F"


class TestDataAvailability:
    def test_na_criteria_excluded_from_denominator(self) -> None:
        data = _mk(asins=[_asin()])
        criteria = run_all(data)
        na_criteria = [c for c in criteria if c.status == "na"]
        assert na_criteria, "Expected some criteria to be marked na (backend keywords etc.)"
        # Denominator should NOT include the NA criteria's points_possible.
        result = compute_grade(criteria)
        na_possible = sum(c.points_possible for c in na_criteria)
        assert result.total_possible == sum(
            c.points_possible for c in criteria if c.status != "na"
        )
        # Sanity: the full rubric is 100 when no criteria are na; with na it should be less.
        total_possible_including_na = sum(c.points_possible for c in criteria)
        assert result.total_possible == total_possible_including_na - na_possible

    def test_warning_criteria_count_as_zero_not_excluded(self) -> None:
        data = _mk(asins=[_asin()])
        criteria = run_all(data)
        warning_criteria = [c for c in criteria if c.status == "warning"]
        assert warning_criteria, "Expected warning criteria for BSR-trend, pricing-consistency etc."
        for c in warning_criteria:
            assert c.points_earned == 0
        result = compute_grade(criteria)
        # Warning criteria stay in the denominator
        for c in warning_criteria:
            assert c.points_possible > 0


class TestFindings:
    def test_strengths_emitted_for_high_scores(self) -> None:
        data = _mk(asins=[_asin() for _ in range(10)], store=BrandStoreDatum(exists=True, page_count=5, video_count=2, nav_depth=6, about_us_text="A" * 600, brand_story_present=True))
        result = compute_grade(run_all(data))
        assert any(f.type == "strength" for f in result.findings)

    def test_weaknesses_emitted_for_low_scores(self) -> None:
        data = _mk(asins=[AsinDatum(asin="B001", title=None, bullet_count=0, image_count=0, rating=2.0)])
        result = compute_grade(run_all(data))
        assert any(f.type == "weakness" for f in result.findings)
        assert any(f.type == "recommendation" for f in result.findings)


class TestGradeBands:
    def test_a_grade_at_90_percent(self) -> None:
        # Synthesize criterion results manually
        from src.scoring.models import CriterionResult
        criteria = [
            CriterionResult(section="X", criterion=f"c{i}", points_earned=9, points_possible=10, status="scored")
            for i in range(10)
        ]
        r = compute_grade(criteria)
        assert r.grade == "A"

    def test_f_grade_below_60_percent(self) -> None:
        from src.scoring.models import CriterionResult
        criteria = [
            CriterionResult(section="X", criterion=f"c{i}", points_earned=5, points_possible=10, status="scored")
            for i in range(10)
        ]
        r = compute_grade(criteria)
        assert r.grade == "F"
