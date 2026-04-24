"""Model pricing table + cost calculation.

Prices are USD per 1,000,000 tokens. Keep this file as the SINGLE source of truth so
audits of "why did this call cost $X" can trace cleanly.

Update when Anthropic pricing changes or a new model is added.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float


# Canonical map. Keys are the full model identifiers passed to the Anthropic API.
# These are approximate 2026 prices — adjust to match current Anthropic pricing.
_PRICES: dict[str, ModelPrice] = {
    # Sonnet family
    "claude-sonnet-4-6": ModelPrice(input_per_mtok=3.0, output_per_mtok=15.0),
    "claude-sonnet-4-7": ModelPrice(input_per_mtok=3.0, output_per_mtok=15.0),
    # Haiku family
    "claude-haiku-4-5-20251001": ModelPrice(input_per_mtok=0.25, output_per_mtok=1.25),
    # Opus family
    "claude-opus-4-7": ModelPrice(input_per_mtok=15.0, output_per_mtok=75.0),
}


# Fallback price for unknown models — we'd rather over-estimate cost than miss it.
_DEFAULT_PRICE = ModelPrice(input_per_mtok=15.0, output_per_mtok=75.0)


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a call. Never negative, rounded to 6 decimals."""
    price = _PRICES.get(model, _DEFAULT_PRICE)
    total = (input_tokens / 1_000_000) * price.input_per_mtok + (
        output_tokens / 1_000_000
    ) * price.output_per_mtok
    return round(max(total, 0.0), 6)


def known_models() -> list[str]:
    return list(_PRICES.keys())
