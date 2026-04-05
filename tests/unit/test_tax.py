"""Tests for Tax service: US tax bracket calculations and classification."""

from decimal import Decimal

import pytest

from services.tax.src.us_tax import USTaxCalculator, TaxEstimate
from services.tax.src.tax_brackets import get_rate, SHORT_TERM_RATES, LONG_TERM_RATES


# ---------------------------------------------------------------------------
# get_rate tests
# ---------------------------------------------------------------------------

class TestGetRate:
    def test_short_term_known_bracket(self):
        assert get_rate(True, "22") == Decimal("0.22")

    def test_short_term_conservative_default(self):
        assert get_rate(True, None) == Decimal("0.37")

    def test_short_term_unknown_bracket_defaults(self):
        assert get_rate(True, "99") == Decimal("0.37")

    def test_long_term_known_bracket(self):
        assert get_rate(False, "15") == Decimal("0.15")

    def test_long_term_conservative_default(self):
        assert get_rate(False, None) == Decimal("0.20")

    def test_long_term_zero_bracket(self):
        assert get_rate(False, "0") == Decimal("0")

    def test_all_short_term_brackets_present(self):
        expected = {"10", "12", "22", "24", "32", "35", "37"}
        assert set(SHORT_TERM_RATES.keys()) == expected

    def test_all_long_term_brackets_present(self):
        expected = {"0", "15", "20"}
        assert set(LONG_TERM_RATES.keys()) == expected


# ---------------------------------------------------------------------------
# USTaxCalculator tests
# ---------------------------------------------------------------------------

class TestUSTaxCalculator:
    def test_short_term_gain(self):
        result = USTaxCalculator.calculate(100, Decimal("10000"), "22")
        assert result.classification == "short-term"
        assert result.effective_rate == Decimal("0.22")
        assert result.estimated_tax == Decimal("2200")

    def test_long_term_gain(self):
        result = USTaxCalculator.calculate(400, Decimal("10000"), "15")
        assert result.classification == "long-term"
        assert result.effective_rate == Decimal("0.15")
        assert result.estimated_tax == Decimal("1500")

    def test_boundary_365_is_long_term(self):
        result = USTaxCalculator.calculate(365, Decimal("1000"), "15")
        assert result.classification == "long-term"

    def test_boundary_364_is_short_term(self):
        result = USTaxCalculator.calculate(364, Decimal("1000"), "22")
        assert result.classification == "short-term"

    def test_zero_pnl_returns_none(self):
        result = USTaxCalculator.calculate(100, Decimal("0"), "22")
        assert result.classification == "none"
        assert result.estimated_tax == Decimal("0")
        assert result.effective_rate == Decimal("0")

    def test_negative_pnl_returns_none(self):
        result = USTaxCalculator.calculate(100, Decimal("-5000"), "22")
        assert result.classification == "none"
        assert result.estimated_tax == Decimal("0")

    def test_no_bracket_uses_conservative(self):
        result = USTaxCalculator.calculate(100, Decimal("10000"))
        assert result.effective_rate == Decimal("0.37")
        assert result.estimated_tax == Decimal("3700")

    def test_result_is_dataclass(self):
        result = USTaxCalculator.calculate(100, Decimal("1000"), "22")
        assert isinstance(result, TaxEstimate)
        assert isinstance(result.estimated_tax, Decimal)
        assert isinstance(result.effective_rate, Decimal)
