"""Tests for the single-source-of-truth notional helper."""

from decimal import Decimal

import pytest

from libs.core.notional import (
    DEFAULT_ALLOCATION_PCT,
    DEFAULT_NOTIONAL_USD,
    NOTIONAL_PER_ALLOC_UNIT_USD,
    profile_notional,
)


class TestConstants:
    def test_defaults_are_decimal(self):
        assert isinstance(NOTIONAL_PER_ALLOC_UNIT_USD, Decimal)
        assert isinstance(DEFAULT_ALLOCATION_PCT, Decimal)
        assert isinstance(DEFAULT_NOTIONAL_USD, Decimal)

    def test_default_notional_matches_alloc_unit_at_alloc_one(self):
        assert DEFAULT_NOTIONAL_USD == DEFAULT_ALLOCATION_PCT * NOTIONAL_PER_ALLOC_UNIT_USD

    def test_default_notional_is_ten_thousand(self):
        # Explicit assertion so a future bump to the constant trips here
        # and forces an audit (per DECISIONS.md 2026-05-05).
        assert DEFAULT_NOTIONAL_USD == Decimal("10000")


class TestProfileNotional:
    def test_string_allocation_pct(self):
        assert profile_notional({"allocation_pct": "1.0"}) == Decimal("10000")

    def test_decimal_allocation_pct(self):
        assert profile_notional({"allocation_pct": Decimal("2.5")}) == Decimal("25000")

    def test_int_allocation_pct(self):
        assert profile_notional({"allocation_pct": 3}) == Decimal("30000")

    def test_float_allocation_pct(self):
        # Floats coerce via str() to avoid binary-float artefacts in Decimal.
        assert profile_notional({"allocation_pct": 0.5}) == Decimal("5000")

    def test_none_profile_returns_default(self):
        assert profile_notional(None) == DEFAULT_NOTIONAL_USD

    def test_empty_dict_returns_default(self):
        assert profile_notional({}) == DEFAULT_NOTIONAL_USD

    def test_missing_key_returns_default(self):
        assert profile_notional({"profile_id": "abc"}) == DEFAULT_NOTIONAL_USD

    def test_explicit_none_value_returns_default(self):
        assert profile_notional({"allocation_pct": None}) == DEFAULT_NOTIONAL_USD

    def test_zero_returns_default(self):
        # Zero allocation isn't a meaningful trading state — return default
        # to keep division-by-notional callers safe. Use is_active=false to
        # actually pause a profile.
        assert profile_notional({"allocation_pct": 0}) == DEFAULT_NOTIONAL_USD
        assert profile_notional({"allocation_pct": "0"}) == DEFAULT_NOTIONAL_USD

    def test_negative_returns_default(self):
        assert profile_notional({"allocation_pct": -1}) == DEFAULT_NOTIONAL_USD
        assert profile_notional({"allocation_pct": Decimal("-2.5")}) == DEFAULT_NOTIONAL_USD

    def test_garbage_string_returns_default(self):
        assert profile_notional({"allocation_pct": "garbage"}) == DEFAULT_NOTIONAL_USD

    def test_unparseable_type_returns_default(self):
        assert profile_notional({"allocation_pct": object()}) == DEFAULT_NOTIONAL_USD

    def test_never_returns_zero_or_negative(self):
        # Property: every valid/invalid input returns a strictly positive Decimal.
        for raw in [None, 0, -1, "0", "-2", "garbage", object(), {}]:
            profile = {"allocation_pct": raw} if raw is not None else None
            assert profile_notional(profile) > 0
