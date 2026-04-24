"""Unit tests for the model pricing table.

Ensures cost math doesn't drift silently when prices are adjusted.
"""

from __future__ import annotations

import pytest

from src.pricing import cost_for, known_models


class TestPricing:
    def test_sonnet_costs_are_plausible(self) -> None:
        # 1M in, 1M out on Sonnet should be in the tens of dollars range.
        c = cost_for("claude-sonnet-4-6", 1_000_000, 1_000_000)
        assert 5.0 < c < 50.0

    def test_haiku_is_cheaper_than_sonnet(self) -> None:
        sonnet = cost_for("claude-sonnet-4-6", 1_000_000, 1_000_000)
        haiku = cost_for("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
        assert haiku < sonnet

    def test_zero_tokens_is_zero_cost(self) -> None:
        assert cost_for("claude-sonnet-4-6", 0, 0) == 0.0

    def test_unknown_model_falls_back_to_expensive(self) -> None:
        # Unknown model should cost at least as much as Sonnet (conservative estimate).
        unknown = cost_for("claude-mystery-9000", 1_000_000, 1_000_000)
        sonnet = cost_for("claude-sonnet-4-6", 1_000_000, 1_000_000)
        assert unknown >= sonnet

    def test_cost_rounded_to_six_decimals(self) -> None:
        # 123 input tokens on Sonnet is a tiny amount; should not return raw float.
        c = cost_for("claude-sonnet-4-6", 123, 45)
        # Number of decimal digits should be <= 6
        assert len(str(c).split(".")[-1]) <= 6

    @pytest.mark.parametrize("model", known_models())
    def test_all_known_models_compute_nonnegative(self, model: str) -> None:
        c = cost_for(model, 100, 100)
        assert c >= 0
