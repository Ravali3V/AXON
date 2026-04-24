"""POST /v1/messages — the one route every AXON service calls.

Flow:
  1. Parse + validate request (Anthropic shape + AXON metadata).
  2. Per-audit cost cap check: sum cost_usd so far; if already >= cap, reject 402.
  3. Dispatch: stub mode (no Anthropic key) returns a canned response; live mode
     forwards to Anthropic via the official SDK.
  4. Compute cost. Insert ai_usage_logs BEFORE returning.
  5. On Anthropic error: still log (success=false) so the cost dashboard sees the call.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from anthropic import AsyncAnthropic, APIError
from fastapi import APIRouter, HTTPException, status

from ..config import get_settings
from ..db import audit_cost_to_date, insert_ai_usage_log
from ..pricing import cost_for
from ..schemas import MessagesRequest, MessagesResponse, UsageBlock

log = structlog.get_logger(__name__)
router = APIRouter()


# Lazily-created SDK client. Only created when stub_mode is False.
_client: AsyncAnthropic | None = None


def _client_or_none() -> AsyncAnthropic | None:
    global _client
    settings = get_settings()
    if settings.stub_mode:
        return None
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url)
    return _client


def _stub_response(req: MessagesRequest) -> tuple[str, list[dict[str, Any]], str, int, int]:
    """Return a deterministic canned response for development without an API key."""
    fake_id = f"msg_stub_{uuid.uuid4().hex[:16]}"
    text = (
        "[STUB RESPONSE — AI_PROXY_STUB_MODE] "
        f"Pretend narrative for purpose={req.axon.purpose} model={req.model}. "
        "Drop a real ANTHROPIC_API_KEY into .env to enable live calls."
    )
    content = [{"type": "text", "text": text}]
    # Deterministic fake token counts so cost shows up in logs.
    input_tokens = sum(len(str(m.content)) for m in req.messages) // 4 + 50
    output_tokens = 120
    return fake_id, content, "end_turn", input_tokens, output_tokens


async def _call_live(req: MessagesRequest) -> tuple[str, list[dict[str, Any]], str | None, int, int]:
    client = _client_or_none()
    assert client is not None, "live path called with no client"

    messages_payload = [{"role": m.role, "content": m.content} for m in req.messages if m.role != "system"]
    system = req.system or next((m.content for m in req.messages if m.role == "system"), None)

    try:
        resp = await client.messages.create(
            model=req.model,
            max_tokens=req.max_tokens,
            messages=messages_payload,  # type: ignore[arg-type]
            **({"system": system} if isinstance(system, str) else {}),
            **({"temperature": req.temperature} if req.temperature is not None else {}),
        )
    except APIError as exc:  # pragma: no cover — integration tested
        log.error("anthropic_api_error", error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    content_blocks: list[dict[str, Any]] = []
    for block in resp.content:
        if hasattr(block, "model_dump"):
            content_blocks.append(block.model_dump())
        else:
            content_blocks.append(dict(block))  # type: ignore[arg-type]

    return (
        resp.id,
        content_blocks,
        resp.stop_reason,
        resp.usage.input_tokens,
        resp.usage.output_tokens,
    )


@router.post("/messages", response_model=MessagesResponse)
async def create_message(req: MessagesRequest) -> MessagesResponse:
    settings = get_settings()

    # ---- cost cap ----
    if req.axon.audit_id:
        spent = await audit_cost_to_date(org_id=req.axon.org_id, audit_id=req.axon.audit_id)
        if spent >= settings.ai_proxy_per_audit_cost_cap_usd:
            # Log the rejection so the dashboard sees it.
            await insert_ai_usage_log(
                entry={
                    "org_id": req.axon.org_id,
                    "audit_id": req.axon.audit_id,
                    "model": req.model,
                    "provider": "rejected",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "latency_ms": 0,
                    "purpose": req.axon.purpose,
                    "success": False,
                    "error_message": f"per-audit cost cap hit: {spent:.6f} >= {settings.ai_proxy_per_audit_cost_cap_usd:.2f}",
                }
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Per-audit cost cap reached (${spent:.4f} spent >= "
                    f"${settings.ai_proxy_per_audit_cost_cap_usd:.2f} cap)."
                ),
            )

    # ---- dispatch ----
    provider = "stub" if settings.stub_mode else "anthropic"
    t0 = time.perf_counter()
    success = True
    error_message: str | None = None
    try:
        if settings.stub_mode:
            msg_id, content, stop_reason, input_tokens, output_tokens = _stub_response(req)
        else:
            msg_id, content, stop_reason, input_tokens, output_tokens = await _call_live(req)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        success = False
        error_message = str(exc)
        msg_id = f"msg_error_{uuid.uuid4().hex[:12]}"
        content = [{"type": "text", "text": ""}]
        stop_reason = "error"
        input_tokens = 0
        output_tokens = 0
    latency_ms = int((time.perf_counter() - t0) * 1000)

    cost_usd = cost_for(req.model, input_tokens, output_tokens)

    # ---- log BEFORE returning ----
    await insert_ai_usage_log(
        entry={
            "org_id": req.axon.org_id,
            "audit_id": req.axon.audit_id,
            "model": req.model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "purpose": req.axon.purpose,
            "success": success,
            "error_message": error_message,
        }
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=error_message or "upstream error")

    return MessagesResponse(
        id=msg_id,
        model=req.model,
        content=content,
        stop_reason=stop_reason,
        usage=UsageBlock(input_tokens=input_tokens, output_tokens=output_tokens),
        axon={
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "provider": provider,
            "purpose": req.axon.purpose,
        },
    )
