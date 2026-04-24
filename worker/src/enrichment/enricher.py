"""LLM enrichment stage — runs after scoring.

Produces:
  1. A narrative summary (Sonnet) — saved as an audit_finding of type recommendation? No,
     saved to audits.narrative (we'll add a column? Actually, write it as a special
     finding with source='llm' and type='recommendation' for now, tagged section=
     '_narrative'. T-13 report viewer pulls that specifically.)
  2. Refined recommendations (Sonnet) — replaces rule-based rec texts with sharpened ones.
  3. Review sentiment + themes (Haiku, batched) — updates audit_reviews.sentiment / themes.

Every call goes through the AI Proxy. If the proxy is in stub mode (no Anthropic key),
all calls return canned strings — we handle that gracefully: we log the stub response
as a finding and move on.

Resilient to failures: if a particular LLM call fails, we emit a warning event and
continue to the next — scoring stays valid, PDF renders without the enrichment.
"""

from __future__ import annotations

import json
import re
from typing import Any

import asyncpg  # type: ignore[import-not-found]
import httpx
import structlog

from ..config import get_settings
from ..db import emit_event, with_tenant
from .client import call_claude
from .prompts import narrative_prompt, recommendation_prompt, sentiment_prompt

log = structlog.get_logger(__name__)


_NARRATIVE_SECTION = "_narrative"  # special section label — not a real rubric section


async def enrich_audit(*, audit_id: str, org_id: str) -> None:
    settings = get_settings()
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="enrich",
        message="Generating narrative and refining recommendations via AI Proxy.",
    )

    try:
        payload = await _assemble_payload(audit_id=audit_id, org_id=org_id)
    except Exception as exc:
        log.exception("enrich_payload_failed", audit_id=audit_id)
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="enrich",
            message=f"Could not assemble enrichment payload: {exc}",
            level="warn",
        )
        return

    # 1) Narrative
    try:
        sys, usr = narrative_prompt(payload)
        narrative = await call_claude(
            model=settings.anthropic_model_sonnet,
            messages=[{"role": "user", "content": usr}],
            system=sys,
            org_id=org_id,
            audit_id=audit_id,
            purpose="report_narrative",
            max_tokens=1200,
        )
        if narrative:
            await _store_narrative(audit_id=audit_id, org_id=org_id, narrative=narrative)
            await emit_event(
                org_id=org_id,
                audit_id=audit_id,
                stage="enrich",
                message=f"Narrative generated ({len(narrative)} chars).",
            )
    except httpx.HTTPError as exc:
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="enrich",
            message=f"Narrative generation failed (continuing without it): {exc}",
            level="warn",
        )

    # 2) Refined recommendations
    try:
        rule_recs = await _load_rule_recs(audit_id=audit_id, org_id=org_id)
        if rule_recs:
            sys, usr = recommendation_prompt(payload.get("brand_name", ""), rule_recs)
            refined_raw = await call_claude(
                model=settings.anthropic_model_sonnet,
                messages=[{"role": "user", "content": usr}],
                system=sys,
                org_id=org_id,
                audit_id=audit_id,
                purpose="recommendations",
                max_tokens=2000,
            )
            refined = _safe_parse_json(refined_raw)
            if refined and isinstance(refined.get("recommendations"), list):
                await _store_refined_recs(
                    audit_id=audit_id,
                    org_id=org_id,
                    refined=refined["recommendations"],
                )
                await emit_event(
                    org_id=org_id,
                    audit_id=audit_id,
                    stage="enrich",
                    message=f"Refined {len(refined['recommendations'])} recommendations.",
                )
    except httpx.HTTPError as exc:
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="enrich",
            message=f"Recommendation refinement failed (continuing): {exc}",
            level="warn",
        )

    # 3) Review sentiment (Haiku, batched)
    try:
        await _classify_reviews(audit_id=audit_id, org_id=org_id)
    except httpx.HTTPError as exc:
        await emit_event(
            org_id=org_id,
            audit_id=audit_id,
            stage="enrich",
            message=f"Review sentiment classification failed (continuing): {exc}",
            level="warn",
        )


async def _assemble_payload(*, audit_id: str, org_id: str) -> dict[str, Any]:
    async def _load(conn: asyncpg.Connection) -> dict[str, Any]:
        audit = await conn.fetchrow(
            "SELECT brand_name, score_total, score_possible, grade FROM audits WHERE id = $1",
            audit_id,
        )
        scores = await conn.fetch(
            """
            SELECT section, criterion, points_earned, points_possible, status
            FROM audit_scores WHERE audit_id = $1
            ORDER BY section, criterion
            """,
            audit_id,
        )
        sections: dict[str, dict[str, Any]] = {}
        for row in scores:
            bucket = sections.setdefault(
                row["section"], {"earned": 0.0, "possible": 0.0, "criteria": []}
            )
            bucket["earned"] += float(row["points_earned"])
            bucket["possible"] += float(row["points_possible"])
            bucket["criteria"].append(
                {
                    "criterion": row["criterion"],
                    "points": f"{row['points_earned']}/{row['points_possible']}",
                    "status": row["status"],
                }
            )
        total_earned = float(audit["score_total"] or 0) if audit else 0.0
        total_possible = float(audit["score_possible"] or 0) if audit else 0.0
        pct = (total_earned / total_possible * 100) if total_possible else 0.0
        return {
            "brand_name": audit["brand_name"] if audit else "",
            "total_earned": total_earned,
            "total_possible": total_possible,
            "percentage": round(pct, 1),
            "grade": audit["grade"] if audit else None,
            "sections": sections,
        }

    return await with_tenant(org_id, _load)


async def _load_rule_recs(*, audit_id: str, org_id: str) -> list[dict[str, Any]]:
    async def _load(conn: asyncpg.Connection) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT id, section, text, priority FROM audit_findings
            WHERE audit_id = $1 AND type IN ('recommendation', 'quick_win')
              AND source = 'rule'
            ORDER BY priority
            """,
            audit_id,
        )
        return [
            {"id": str(r["id"]), "section": r["section"], "text": r["text"], "priority": r["priority"]}
            for r in rows
        ]

    return await with_tenant(org_id, _load)


async def _store_narrative(*, audit_id: str, org_id: str, narrative: str) -> None:
    async def _do(conn: asyncpg.Connection) -> None:
        # Clean out any prior LLM narrative finding first (idempotent re-enrichment).
        await conn.execute(
            """
            DELETE FROM audit_findings
            WHERE audit_id = $1 AND source = 'llm' AND section = $2
            """,
            audit_id,
            _NARRATIVE_SECTION,
        )
        await conn.execute(
            """
            INSERT INTO audit_findings (
                audit_id, org_id, type, section, text, priority, source
            ) VALUES ($1, $2, 'recommendation', $3, $4, 1, 'llm')
            """,
            audit_id,
            org_id,
            _NARRATIVE_SECTION,
            narrative,
        )

    await with_tenant(org_id, _do)


async def _store_refined_recs(
    *, audit_id: str, org_id: str, refined: list[dict[str, Any]]
) -> None:
    async def _do(conn: asyncpg.Connection) -> None:
        # Delete prior LLM recommendations (but keep the LLM narrative above).
        await conn.execute(
            """
            DELETE FROM audit_findings
            WHERE audit_id = $1 AND source = 'llm' AND section != $2
            """,
            audit_id,
            _NARRATIVE_SECTION,
        )
        await conn.executemany(
            """
            INSERT INTO audit_findings (
                audit_id, org_id, type, section, text, priority, source
            ) VALUES ($1, $2, 'recommendation', $3, $4, 2, 'llm')
            """,
            [
                (audit_id, org_id, str(r.get("section", "General")), str(r.get("text", "")))
                for r in refined
                if r.get("text")
            ],
        )

    await with_tenant(org_id, _do)


async def _classify_reviews(*, audit_id: str, org_id: str) -> None:
    settings = get_settings()

    async def _load(conn: asyncpg.Connection) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT id, review_id, rating, title, body FROM audit_reviews
            WHERE audit_id = $1 AND sentiment IS NULL AND body IS NOT NULL
            LIMIT 500
            """,
            audit_id,
        )
        return [
            {
                "id": str(r["id"]),
                "review_id": r["review_id"] or str(r["id"]),
                "rating": r["rating"],
                "title": r["title"],
                "body": (r["body"] or "")[:500],  # trim long bodies to control tokens
            }
            for r in rows
        ]

    reviews = await with_tenant(org_id, _load)
    if not reviews:
        return

    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="enrich",
        message=f"Classifying sentiment for {len(reviews)} reviews (Haiku, batched).",
    )

    batch_size = 40
    updates: list[tuple[str, str, list[str]]] = []

    for start in range(0, len(reviews), batch_size):
        batch = reviews[start : start + batch_size]
        # Reduce what we send — Haiku doesn't need the internal id
        payload = [{"review_id": r["review_id"], "rating": r["rating"], "text": r["body"]} for r in batch]
        sys, usr = sentiment_prompt(payload)
        try:
            raw = await call_claude(
                model=settings.anthropic_model_haiku,
                messages=[{"role": "user", "content": usr}],
                system=sys,
                org_id=org_id,
                audit_id=audit_id,
                purpose="review_sentiment",
                max_tokens=2000,
            )
            parsed = _safe_parse_json(raw)
            if not parsed:
                continue
            by_rid = {r["review_id"]: r for r in batch}
            for item in parsed.get("results", []):
                rid = item.get("review_id")
                sentiment = item.get("sentiment")
                themes = item.get("themes") or []
                if rid and rid in by_rid and sentiment in ("positive", "neutral", "negative"):
                    src = by_rid[rid]
                    updates.append(
                        (src["id"], sentiment, [str(t)[:80] for t in themes if t][:5])
                    )
        except httpx.HTTPError as exc:
            log.warning("sentiment_batch_failed", batch_start=start, error=str(exc))
            continue

    if not updates:
        return

    async def _persist(conn: asyncpg.Connection) -> None:
        await conn.executemany(
            """
            UPDATE audit_reviews SET sentiment = $2, themes = $3
            WHERE id = $1
            """,
            updates,
        )

    await with_tenant(org_id, _persist)
    await emit_event(
        org_id=org_id,
        audit_id=audit_id,
        stage="enrich",
        message=f"Sentiment applied to {len(updates)} reviews.",
    )


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _safe_parse_json(text: str) -> Any:
    """Extract JSON from a Claude response that may include a prose preamble or fences."""
    if not text:
        return None
    # Try verbatim
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json``` fences
    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding the first { ... } span
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(text[first : last + 1])
        except json.JSONDecodeError:
            pass
    return None
