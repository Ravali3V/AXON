"""Unit tests for scrape.parsers — pure text extraction, no browser required."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.scrape.parsers import (
    clean_text,
    parse_bsr,
    parse_price,
    parse_rating,
    parse_review_count,
)


class TestParsePrice:
    def test_plain_dollars(self) -> None:
        assert parse_price("$24.99") == Decimal("24.99")

    def test_dollars_with_space(self) -> None:
        assert parse_price("Price: $ 1,234") in (Decimal("1.234"), Decimal("1234"))
        # Note: comma-as-thousands isn't distinguishable from comma-as-decimal
        # without locale; we accept either numeric interpretation.

    def test_euro_with_comma_decimal(self) -> None:
        assert parse_price("€9,99") == Decimal("9.99")

    def test_none_for_empty(self) -> None:
        assert parse_price("") is None
        assert parse_price(None) is None

    def test_none_when_no_price_pattern(self) -> None:
        assert parse_price("out of stock") is None

    def test_fallback_to_plain_number(self) -> None:
        # When there's no currency symbol, parse_price falls back to a dot-decimal.
        assert parse_price("Buy for 12.50 today") == Decimal("12.50")


class TestParseRating:
    def test_standard_phrase(self) -> None:
        assert parse_rating("4.3 out of 5 stars") == 4.3

    def test_whole_number(self) -> None:
        assert parse_rating("5 out of 5 stars") == 5.0

    def test_none_when_missing(self) -> None:
        assert parse_rating(None) is None
        assert parse_rating("no rating yet") is None

    def test_case_insensitive(self) -> None:
        assert parse_rating("4.0 Out Of 5 stars") == 4.0


class TestParseReviewCount:
    def test_thousands_separator(self) -> None:
        assert parse_review_count("1,234 global ratings") == 1234

    def test_small_count(self) -> None:
        assert parse_review_count("3 ratings") == 3

    def test_reviews_word(self) -> None:
        assert parse_review_count("567 reviews") == 567

    def test_none_when_empty(self) -> None:
        assert parse_review_count(None) is None
        assert parse_review_count("") is None


class TestParseBsr:
    def test_single_category(self) -> None:
        rank, cat = parse_bsr("Best Sellers Rank: #123 in Electronics")
        assert rank == 123
        assert cat == "Electronics"

    def test_commas_in_rank(self) -> None:
        rank, cat = parse_bsr("#1,234 in Home & Kitchen")
        assert rank == 1234
        assert cat == "Home & Kitchen"

    def test_multiple_categories_returns_first(self) -> None:
        text = "#123 in Electronics (See Top 100 in Electronics) #4 in USB Hubs"
        rank, cat = parse_bsr(text)
        assert rank == 123
        assert cat == "Electronics"

    def test_no_match(self) -> None:
        rank, cat = parse_bsr("Product not ranked")
        assert rank is None
        assert cat is None

    def test_none_input(self) -> None:
        assert parse_bsr(None) == (None, None)


class TestCleanText:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("  hello  world  ", "hello world"),
            ("\n\tAmazon\n", "Amazon"),
            ("", None),
            (None, None),
            ("already clean", "already clean"),
            ("multi\n\nline\ntext", "multi line text"),
        ],
    )
    def test_whitespace_normalization(self, raw: str | None, expected: str | None) -> None:
        assert clean_text(raw) == expected
