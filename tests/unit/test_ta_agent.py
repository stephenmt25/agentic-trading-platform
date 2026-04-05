"""Tests for TA Agent service: multi-timeframe confluence scoring."""

import pytest
from unittest.mock import MagicMock, patch

from services.ta_agent.src.confluence import TAConfluenceScorer


# ---------------------------------------------------------------------------
# TAConfluenceScorer tests
# ---------------------------------------------------------------------------

class TestTAConfluenceScorer:
    def test_timeframes(self):
        assert TAConfluenceScorer.TIMEFRAMES == ("1m", "5m", "15m", "1h")

    def test_score_returns_none_before_warmup(self):
        scorer = TAConfluenceScorer()
        assert scorer.score() is None

    def test_score_returns_none_partial_warmup(self):
        scorer = TAConfluenceScorer()
        # Feed only one timeframe
        for i in range(50):
            scorer.update_timeframe("1m", 101 + i * 0.1, 99 + i * 0.1, 100 + i * 0.1)
        assert scorer.score() is None

    def test_score_after_full_warmup(self):
        scorer = TAConfluenceScorer()
        # Feed all timeframes with enough data
        for tf in TAConfluenceScorer.TIMEFRAMES:
            for i in range(50):
                h = 101 + i * 0.5
                l = 99 + i * 0.5
                c = 100 + i * 0.5
                scorer.update_timeframe(tf, h, l, c)

        score = scorer.score()
        assert score is not None
        assert -1.0 <= score <= 1.0

    def test_score_bounded(self):
        scorer = TAConfluenceScorer()
        # Feed extreme bullish data (steadily rising)
        for tf in TAConfluenceScorer.TIMEFRAMES:
            for i in range(60):
                price = 100 + i * 2.0
                scorer.update_timeframe(tf, price + 1, price - 1, price)

        score = scorer.score()
        if score is not None:
            assert -1.0 <= score <= 1.0

    def test_update_unknown_timeframe_ignored(self):
        scorer = TAConfluenceScorer()
        scorer.update_timeframe("1d", 100, 99, 100)  # not in TIMEFRAMES
        # Should not crash, just ignore

    def test_score_is_rounded(self):
        scorer = TAConfluenceScorer()
        for tf in TAConfluenceScorer.TIMEFRAMES:
            for i in range(50):
                c = 100 + i * 0.3
                scorer.update_timeframe(tf, c + 0.5, c - 0.5, c)

        score = scorer.score()
        if score is not None:
            # Check 4 decimal places max
            assert score == round(score, 4)

    def test_different_data_produces_different_scores(self):
        """Confirm that different price patterns produce distinct scores."""
        scorer_up = TAConfluenceScorer()
        scorer_flat = TAConfluenceScorer()
        for tf in TAConfluenceScorer.TIMEFRAMES:
            for i in range(60):
                # Rising
                p_up = 100 + i * 1.0
                scorer_up.update_timeframe(tf, p_up + 0.5, p_up - 0.5, p_up)
                # Flat with noise
                p_flat = 100.0 + (i % 2) * 0.1
                scorer_flat.update_timeframe(tf, p_flat + 0.5, p_flat - 0.5, p_flat)

        score_up = scorer_up.score()
        score_flat = scorer_flat.score()
        if score_up is not None and score_flat is not None:
            assert score_up != score_flat
