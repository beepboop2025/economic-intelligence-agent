"""Tests for src/utils.py — formatting, safe coercion, JSON extraction, navigation."""

import math

import pytest

import utils


# ── format_number ────────────────────────────────────────────────

class TestFormatNumber:
    def test_thousands_suffix(self):
        assert utils.format_number(1500) == "1.5K"

    def test_billions_suffix(self):
        assert utils.format_number(2_500_000_000) == "2.5B"

    def test_trillions_suffix(self):
        assert utils.format_number(3_200_000_000_000) == "3.2T"

    def test_millions_suffix(self):
        assert utils.format_number(7_250_000, decimals=2) == "7.25M"

    def test_below_thousand_no_suffix(self):
        assert utils.format_number(42) == "42.0"

    def test_zero_is_literal_zero(self):
        # Special-cased: returns "0" with no decimals/suffix.
        assert utils.format_number(0) == "0"

    def test_none_returns_na(self):
        assert utils.format_number(None) == "N/A"

    def test_nan_returns_na(self):
        assert utils.format_number(float("nan")) == "N/A"

    def test_negative_keeps_sign(self):
        assert utils.format_number(-1500) == "-1.5K"

    def test_decimals_argument_respected(self):
        assert utils.format_number(1234, decimals=2) == "1.23K"


# ── format_price ─────────────────────────────────────────────────

class TestFormatPrice:
    def test_large_price_uses_thousand_separators(self):
        assert utils.format_price(12345.6) == "$12,345.60"

    def test_mid_price_two_decimals(self):
        assert utils.format_price(42.5) == "$42.50"

    def test_sub_dollar_uses_four_decimals(self):
        assert utils.format_price(0.25) == "$0.2500"

    def test_micro_price_uses_six_decimals(self):
        assert utils.format_price(0.001234) == "$0.001234"

    def test_zero_price(self):
        assert utils.format_price(0) == "$0.00"

    def test_none_returns_na(self):
        assert utils.format_price(None) == "N/A"

    def test_custom_prefix(self):
        assert utils.format_price(99.99, prefix="€") == "€99.99"


# ── format_percent ───────────────────────────────────────────────

class TestFormatPercent:
    def test_positive_gets_plus_sign(self):
        assert utils.format_percent(3.5) == "+3.50%"

    def test_negative_keeps_minus(self):
        assert utils.format_percent(-2.25) == "-2.25%"

    def test_none_returns_na(self):
        assert utils.format_percent(None) == "N/A"

    def test_non_numeric_string_returns_na(self):
        assert utils.format_percent("abc") == "N/A"

    def test_decimals_argument(self):
        assert utils.format_percent(1.23456, decimals=3) == "+1.235%"


# ── Number (safe coercion) ───────────────────────────────────────

class TestNumber:
    def test_none_becomes_zero(self):
        assert utils.Number(None) == 0.0

    def test_nan_becomes_zero(self):
        assert utils.Number(float("nan")) == 0.0

    def test_numeric_string_parsed(self):
        assert utils.Number("3.14") == pytest.approx(3.14)

    def test_garbage_string_becomes_zero(self):
        assert utils.Number("not-a-number") == 0.0

    def test_passthrough_float(self):
        assert utils.Number(2.5) == 2.5


# ── extract_json_from_text ───────────────────────────────────────

class TestExtractJson:
    def test_plain_json(self):
        assert utils.extract_json_from_text('{"a": 1}') == {"a": 1}

    def test_markdown_fenced_json(self):
        text = "```json\n{\"signal\": \"buy\"}\n```"
        assert utils.extract_json_from_text(text) == {"signal": "buy"}

    def test_json_with_surrounding_prose(self):
        text = 'Here is the result: {"score": 7} — hope that helps!'
        assert utils.extract_json_from_text(text) == {"score": 7}

    def test_nested_braces_inside_string_value(self):
        # The balanced-brace parser must ignore braces that live inside strings.
        text = 'noise {"note": "use {curly} here", "n": 2} trailing'
        assert utils.extract_json_from_text(text) == {"note": "use {curly} here", "n": 2}

    def test_nested_object(self):
        text = 'prefix {"outer": {"inner": 1}} suffix'
        assert utils.extract_json_from_text(text) == {"outer": {"inner": 1}}

    def test_no_brace_returns_none(self):
        assert utils.extract_json_from_text("no json at all") is None

    def test_empty_string_returns_none(self):
        assert utils.extract_json_from_text("") is None

    def test_non_string_returns_none(self):
        assert utils.extract_json_from_text(None) is None

    def test_unbalanced_braces_return_none(self):
        assert utils.extract_json_from_text('{"a": 1') is None


# ── safe_get ─────────────────────────────────────────────────────

class TestSafeGet:
    def test_nested_dict_navigation(self):
        data = {"crypto": {"top_coins": [{"price": 42}]}}
        assert utils.safe_get(data, "crypto", "top_coins", 0, "price") == 42

    def test_missing_key_returns_default(self):
        assert utils.safe_get({"a": 1}, "b", default="fallback") == "fallback"

    def test_index_out_of_range_returns_default(self):
        assert utils.safe_get({"x": [1, 2]}, "x", 9, default=-1) == -1

    def test_indexing_into_non_sequence_returns_default(self):
        assert utils.safe_get({"x": 5}, "x", 0, default="d") == "d"

    def test_default_is_none_by_default(self):
        assert utils.safe_get({}, "missing") is None


# ── truncate ─────────────────────────────────────────────────────

class TestTruncate:
    def test_short_text_unchanged(self):
        assert utils.truncate("hello", max_len=100) == "hello"

    def test_long_text_truncated_with_ellipsis(self):
        result = utils.truncate("x" * 50, max_len=10)
        assert result.endswith("...")
        assert len(result) == 10

    def test_none_becomes_empty_string(self):
        assert utils.truncate(None) == ""

    def test_exact_length_unchanged(self):
        assert utils.truncate("abc", max_len=3) == "abc"
