"""Request / response schemas for /v1/messages.

Mirrors Anthropic's Messages API shape so callers can swap the base URL with minimal
change, while adding required AXON metadata fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AIPurpose = Literal[
    "report_narrative",
    "strengths_weaknesses",
    "recommendations",
    "quick_wins",
    "review_sentiment",
    "listing_copy",
    "anomaly_explain",
    "keyword_score",
    "chat_copilot",
    "other",
]


class MessageContent(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str | list[dict[str, Any]]


class AxonMetadata(BaseModel):
    org_id: str
    audit_id: str | None = None
    purpose: AIPurpose = "other"


class MessagesRequest(BaseModel):
    """Mirrors Anthropic's messages endpoint + AXON metadata envelope."""

    model: str
    messages: list[MessageContent]
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    system: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)

    # AXON additions
    axon: AxonMetadata


class UsageBlock(BaseModel):
    input_tokens: int
    output_tokens: int


class MessagesResponse(BaseModel):
    """Returned to callers. Adds `axon` block with cost/latency telemetry."""

    id: str
    model: str
    content: list[dict[str, Any]]
    stop_reason: str | None = None
    usage: UsageBlock
    axon: dict[str, Any]
