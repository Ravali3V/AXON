"""HTTP client for the AXON AI Proxy.

Every Claude call from the worker goes through this client so we never accidentally
import the Anthropic SDK directly. The proxy handles: auth to Anthropic, cost logging
to ai_usage_logs, per-audit cost cap, and stub mode when no API key is configured.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
import structlog

from ..config import get_settings

log = structlog.get_logger(__name__)


AIPurpose = Literal[
    "report_narrative",
    "strengths_weaknesses",
    "recommendations",
    "quick_wins",
    "review_sentiment",
    "other",
]


async def call_claude(
    *,
    model: str,
    messages: list[dict[str, str]],
    org_id: str,
    audit_id: str,
    purpose: AIPurpose,
    system: str | None = None,
    max_tokens: int = 1024,
    temperature: float | None = 0.3,
) -> str:
    """Send a request to the AI Proxy and return the response text.

    Raises httpx.HTTPStatusError on non-2xx (including 402 cost-cap). Returns empty
    string if the proxy returns no text blocks (shouldn't happen normally).
    """
    settings = get_settings()
    url = f"{settings.ai_proxy_url.rstrip('/')}/v1/messages"

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "axon": {
            "org_id": org_id,
            "audit_id": audit_id,
            "purpose": purpose,
        },
    }
    if system:
        body["system"] = system
    if temperature is not None:
        body["temperature"] = temperature

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

    # Extract text from content blocks (Anthropic shape).
    text_parts: list[str] = []
    for block in data.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(str(block.get("text", "")))
    return "\n".join(text_parts).strip()
