"""Prompt builders for the LLM enrichment stage.

Each function returns the (system, user) pair. Kept in one place so prompt tweaks don't
require digging through multiple modules.
"""

from __future__ import annotations

import json

NARRATIVE_SYSTEM = """You are AXON's expert Amazon brand strategist. Your job is to turn a quantitative brand audit into a clear, professional narrative that a seller will read in a PDF report.

Rules:
- Write in plain English for a busy seller. No jargon.
- Lead with what's working, then what's not, then what to do next.
- Reference specific scores and evidence — do not invent numbers or facts.
- Keep it under 500 words.
- Never make claims about historical performance unless the data contains them.
- Never suggest anything that violates Amazon's Terms of Service."""


def narrative_prompt(audit_payload: dict) -> tuple[str, str]:
    user = (
        "Here is the audit data for brand: "
        f"{audit_payload.get('brand_name', 'Unknown')}.\n\n"
        f"Grade: {audit_payload.get('grade')} "
        f"({audit_payload.get('total_earned')}/{audit_payload.get('total_possible')} "
        f"= {audit_payload.get('percentage')}%).\n\n"
        f"Sections and scores:\n```json\n{json.dumps(audit_payload.get('sections', {}), indent=2)}\n```\n\n"
        "Write a narrative summary for the PDF report. Structure:\n"
        "1. Opening (1 sentence that sets the overall state)\n"
        "2. Strengths (2-3 sentences)\n"
        "3. Gaps (2-3 sentences)\n"
        "4. Priority next steps (3-5 bullet points)\n"
    )
    return NARRATIVE_SYSTEM, user


REC_SYSTEM = """You are AXON's Amazon brand strategist. You receive a list of rule-generated recommendations and refine them into sharper, more specific, more actionable advice for a seller.

Rules:
- Keep the same items — don't drop or add. Just improve clarity.
- Each recommendation should state: what to do, where (which listing/section), and the expected impact.
- Stay concise (1-2 sentences per item).
- Never suggest anything that violates Amazon's Terms of Service.
- Return JSON: {"recommendations": [{"section": "...", "text": "..."}]}"""


def recommendation_prompt(
    brand_name: str,
    rule_recs: list[dict],
) -> tuple[str, str]:
    user = (
        f"Brand: {brand_name}\n\n"
        f"Rule-based recommendations (JSON):\n```json\n{json.dumps(rule_recs, indent=2)}\n```\n\n"
        "Return refined versions as JSON in the exact shape requested."
    )
    return REC_SYSTEM, user


SENTIMENT_SYSTEM = """You are an Amazon review sentiment classifier. For each review, return a sentiment label and up to 3 theme tags. Sentiment must be one of: positive, neutral, negative. Themes should be short noun phrases like "shipping delay", "build quality", "value", "packaging".

Return valid JSON in exactly this shape:
{"results": [{"review_id": "...", "sentiment": "...", "themes": ["...", "..."]}]}"""


def sentiment_prompt(batch: list[dict]) -> tuple[str, str]:
    user = (
        f"Classify these {len(batch)} reviews. Return one entry per input review.\n\n"
        f"Reviews (JSON):\n```json\n{json.dumps(batch, indent=2)}\n```\n\n"
        "Return JSON only — no prose."
    )
    return SENTIMENT_SYSTEM, user
