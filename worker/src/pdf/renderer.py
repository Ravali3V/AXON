"""Orchestrates: load audit data → build report HTML → spawn Node sidecar → upload to GCS.

Called by the pipeline after enrichment is done. Returns the `gs://...` or `file://...`
path that gets written onto `audits.report_pdf_gcs_path`.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-not-found]
import structlog

from ..db import with_tenant
from .storage import store_pdf
from .template import render_report_html

log = structlog.get_logger(__name__)

# Allow overriding where the sidecar lives (e.g. in Docker: /app/pdf_sidecar).
_DEFAULT_SIDECAR = Path(__file__).resolve().parents[2] / "pdf_sidecar" / "render.js"


async def render_and_upload(*, audit_id: str, org_id: str) -> str:
    payload = await _assemble_report_payload(audit_id=audit_id, org_id=org_id)
    html = render_report_html(payload)
    pdf_bytes = await _html_to_pdf(html)
    return await store_pdf(audit_id=audit_id, org_id=org_id, pdf_bytes=pdf_bytes)


async def _html_to_pdf(html: str) -> bytes:
    sidecar_path = Path(os.environ.get("AXON_PDF_SIDECAR", str(_DEFAULT_SIDECAR)))
    if not sidecar_path.exists():
        raise RuntimeError(
            f"PDF sidecar not found at {sidecar_path}. "
            "Run: cd worker/pdf_sidecar && npm install"
        )

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(sidecar_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=html.encode("utf-8"))
    if proc.returncode != 0:
        raise RuntimeError(
            f"PDF sidecar failed (exit {proc.returncode}): {stderr.decode('utf-8', errors='replace')[:2000]}"
        )
    if not stdout or len(stdout) < 200:
        raise RuntimeError("PDF sidecar returned empty output.")
    return stdout


async def _assemble_report_payload(*, audit_id: str, org_id: str) -> dict[str, Any]:
    """Read the audit's scores, findings, ASINs — everything needed by the template."""

    async def _load(conn: asyncpg.Connection) -> dict[str, Any]:
        audit = await conn.fetchrow(
            """
            SELECT brand_name, grade, score_total, score_possible
            FROM audits WHERE id = $1
            """,
            audit_id,
        )
        if not audit:
            return {"brand_name": "", "grade": "F", "total_earned": 0, "total_possible": 0}

        score_rows = await conn.fetch(
            """
            SELECT section, criterion, points_earned, points_possible, status, evidence
            FROM audit_scores WHERE audit_id = $1
            ORDER BY section, criterion
            """,
            audit_id,
        )

        # Group into sections preserving rubric order (approximately — by first-seen section).
        sections: list[dict[str, Any]] = []
        section_index: dict[str, dict[str, Any]] = {}
        for row in score_rows:
            name = row["section"]
            if name not in section_index:
                entry: dict[str, Any] = {
                    "name": name,
                    "earned": 0.0,
                    "possible": 0.0,
                    "criteria": [],
                }
                section_index[name] = entry
                sections.append(entry)
            section_index[name]["earned"] += float(row["points_earned"])
            section_index[name]["possible"] += float(row["points_possible"])
            ev = row["evidence"] or {}
            section_index[name]["criteria"].append(
                {
                    "criterion": row["criterion"],
                    "points_earned": float(row["points_earned"]),
                    "points_possible": float(row["points_possible"]),
                    "status": row["status"],
                    "evidence_summary": _short_evidence(ev),
                }
            )

        for s in sections:
            s["earned"] = round(s["earned"], 1)
            s["possible"] = round(s["possible"], 1)

        # Findings — split by type
        finding_rows = await conn.fetch(
            """
            SELECT type, section, text, source, priority
            FROM audit_findings WHERE audit_id = $1
            ORDER BY priority ASC, section
            """,
            audit_id,
        )
        # LLM narrative is stored as a finding with section='_narrative'
        narrative = ""
        strengths: list[dict[str, Any]] = []
        weaknesses: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []
        quick_wins: list[dict[str, Any]] = []
        for row in finding_rows:
            item = {
                "section": row["section"] if row["section"] != "_narrative" else "",
                "text": row["text"],
            }
            if row["source"] == "llm" and row["section"] == "_narrative":
                narrative = row["text"]
                continue
            if row["type"] == "strength":
                strengths.append(item)
            elif row["type"] == "weakness":
                weaknesses.append(item)
            elif row["type"] == "recommendation":
                recommendations.append(item)
            elif row["type"] == "quick_win":
                quick_wins.append(item)

        asin_rows = await conn.fetch(
            """
            SELECT asin, title, bsr, rating, review_count, image_count, bullet_count,
                   has_aplus, has_brand_story, has_video, buybox_seller,
                   bsr_category,
                   raw->>'main_image_url' AS main_image_url
            FROM audit_asins WHERE audit_id = $1
            ORDER BY bsr NULLS LAST
            LIMIT 200
            """,
            audit_id,
        )
        asins = [
            {
                "asin": r["asin"],
                "title": r["title"] or "",
                "bsr": r["bsr"],
                "bsr_category": r["bsr_category"],
                "rating": float(r["rating"]) if r["rating"] is not None else None,
                "review_count": r["review_count"],
                "image_count": r["image_count"] or 0,
                "bullet_count": r["bullet_count"] or 0,
                "has_aplus": bool(r["has_aplus"]),
                "has_brand_story": bool(r["has_brand_story"]),
                "has_video": bool(r["has_video"]),
                "buybox_seller": r["buybox_seller"],
                "main_image_url": r["main_image_url"],
            }
            for r in asin_rows
        ]

        # Brand store about_us_text for cover page
        bs_row = await conn.fetchrow(
            "SELECT brand_store_json FROM audit_brand_data WHERE audit_id = $1 ORDER BY scraped_at DESC LIMIT 1",
            audit_id,
        )
        about_us_text = ""
        if bs_row:
            raw_bs = bs_row["brand_store_json"] or {}
            if isinstance(raw_bs, str):
                try:
                    raw_bs = json.loads(raw_bs)
                except Exception:
                    raw_bs = {}
            about_us_text = raw_bs.get("about_us_text") or ""

        total_earned = float(audit["score_total"] or 0)
        total_possible = float(audit["score_possible"] or 0)
        pct = (total_earned / total_possible * 100) if total_possible else 0.0

        return {
            "brand_name": audit["brand_name"],
            "grade": audit["grade"] or "Untapped",
            "total_earned": total_earned,
            "total_possible": total_possible,
            "percentage": round(pct, 1),
            "narrative": narrative,
            "sections": sections,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "quick_wins": quick_wins,
            "asins": asins,
            "about_us_text": about_us_text,
        }

    return await with_tenant(org_id, _load)


def _short_evidence(evidence: Any) -> str:
    """Render evidence JSON as a short one-liner for the PDF table cell."""
    if not evidence:
        return ""
    if isinstance(evidence, str):
        # asyncpg returns jsonb as Python dict, but defensive
        try:
            evidence = json.loads(evidence)
        except Exception:
            return evidence[:80]
    if isinstance(evidence, dict):
        parts = []
        for k, v in list(evidence.items())[:4]:
            parts.append(f"{k}={v}")
        return ", ".join(parts)[:120]
    return str(evidence)[:120]
