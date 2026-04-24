"""Scoring engine — reads scraped data, runs the rubric, writes scores + findings.

Call `score_audit(audit_id, org_id)` once scraping stages have completed.
"""

from __future__ import annotations

import asyncpg  # type: ignore[import-not-found]
import structlog

from ..db import emit_event, set_audit_status, with_tenant
from .models import (
    AsinDatum,
    AuditData,
    BrandStoreDatum,
    Finding,
    ReviewDatum,
)
from .rubric import compute_grade, run_all

log = structlog.get_logger(__name__)


async def score_audit(*, audit_id: str, org_id: str) -> None:
    """Load scraped data, compute rubric, persist scores + findings, update audit row."""
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scoring",
        message="Loading scraped data for scoring.",
    )
    await set_audit_status(org_id=org_id, audit_id=audit_id, status="scoring")

    data = await _load_audit_data(audit_id=audit_id, org_id=org_id)
    criteria = run_all(data)
    result = compute_grade(criteria)

    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="scoring",
        message=(
            f"Scoring complete: {result.total_earned}/{result.total_possible} "
            f"({result.percentage:.1f}%) grade {result.grade}"
        ),
    )

    await _persist_scores_and_findings(
        audit_id=audit_id,
        org_id=org_id,
        criteria=criteria,
        findings=result.findings,
    )

    await set_audit_status(
        org_id=org_id,
        audit_id=audit_id,
        status="enriching",
        score_total=int(round(result.total_earned)),
        score_possible=int(round(result.total_possible)),
        grade=result.grade,
    )


async def _load_audit_data(*, audit_id: str, org_id: str) -> AuditData:
    async def _load(conn: asyncpg.Connection) -> AuditData:
        audit_row = await conn.fetchrow(
            "SELECT brand_name FROM audits WHERE id = $1", audit_id
        )
        brand_name = audit_row["brand_name"] if audit_row else ""

        asin_rows = await conn.fetch(
            """
            SELECT asin, title, bullet_count, has_aplus, has_brand_story, has_video,
                   image_count, rating, review_count, bsr, bsr_category, buybox_seller,
                   variation_parent_asin, price,
                   raw->>'description' AS description,
                   COALESCE((raw->>'aplus_module_count')::int, 0) AS aplus_module_count
            FROM audit_asins WHERE audit_id = $1
            """,
            audit_id,
        )
        asins: list[AsinDatum] = []
        for r in asin_rows:
            asins.append(
                AsinDatum(
                    asin=r["asin"],
                    title=r["title"],
                    bullet_count=r["bullet_count"] or 0,
                    description=r["description"],
                    image_count=r["image_count"] or 0,
                    aplus_module_count=r["aplus_module_count"] or 0,
                    has_aplus=bool(r["has_aplus"]),
                    has_brand_story=bool(r["has_brand_story"]),
                    has_video=bool(r["has_video"]),
                    rating=float(r["rating"]) if r["rating"] is not None else None,
                    review_count=r["review_count"],
                    bsr=r["bsr"],
                    bsr_category=r["bsr_category"],
                    buybox_seller=r["buybox_seller"],
                    variation_parent_asin=r["variation_parent_asin"],
                    price=float(r["price"]) if r["price"] is not None else None,
                )
            )

        review_rows = await conn.fetch(
            "SELECT asin, rating, verified, body FROM audit_reviews WHERE audit_id = $1",
            audit_id,
        )
        reviews = [
            ReviewDatum(
                asin=r["asin"],
                rating=r["rating"],
                verified=bool(r["verified"]),
                body=r["body"],
            )
            for r in review_rows
        ]

        bs_row = await conn.fetchrow(
            """
            SELECT brand_store_url, brand_store_json, brand_story_detected, video_count
            FROM audit_brand_data WHERE audit_id = $1
            ORDER BY scraped_at DESC LIMIT 1
            """,
            audit_id,
        )
        brand_store = BrandStoreDatum()
        if bs_row:
            raw = bs_row["brand_store_json"] or {}
            if isinstance(raw, str):
                import json as _json
                raw = _json.loads(raw) if raw else {}
            brand_store = BrandStoreDatum(
                exists=bool(bs_row["brand_store_url"]),
                store_url=bs_row["brand_store_url"],
                page_count=int(raw.get("page_count", 0)),
                video_count=int(bs_row["video_count"] or 0),
                nav_depth=int(raw.get("nav_depth", 0)),
                about_us_text=raw.get("about_us_text"),
                brand_story_present=bool(bs_row["brand_story_detected"]),
                product_tile_count=int(raw.get("product_tile_count", 0)),
                has_hero=bool(raw.get("has_hero", False)),
            )

        return AuditData(
            brand_name=brand_name,
            asins=asins,
            reviews=reviews,
            brand_store=brand_store,
        )

    return await with_tenant(org_id, _load)


async def _persist_scores_and_findings(
    *,
    audit_id: str,
    org_id: str,
    criteria,
    findings: list[Finding],
) -> None:
    import json

    async def _do(conn: asyncpg.Connection) -> None:
        # Clear prior scores/findings so re-scoring replaces cleanly.
        await conn.execute("DELETE FROM audit_scores WHERE audit_id = $1", audit_id)
        await conn.execute(
            "DELETE FROM audit_findings WHERE audit_id = $1 AND source = 'rule'",
            audit_id,
        )

        await conn.executemany(
            """
            INSERT INTO audit_scores (
                audit_id, org_id, section, criterion,
                points_earned, points_possible, status, evidence
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            """,
            [
                (
                    audit_id,
                    org_id,
                    c.section,
                    c.criterion,
                    c.points_earned,
                    c.points_possible,
                    c.status,
                    json.dumps(c.evidence),
                )
                for c in criteria
            ],
        )
        await conn.executemany(
            """
            INSERT INTO audit_findings (
                audit_id, org_id, type, section, text, priority, source
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            [
                (audit_id, org_id, f.type, f.section, f.text, f.priority, f.source)
                for f in findings
            ],
        )

    await with_tenant(org_id, _do)
