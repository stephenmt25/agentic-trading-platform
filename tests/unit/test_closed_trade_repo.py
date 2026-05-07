"""Unit tests for ClosedTradeRepository.

Verifies the repo constructs the expected SQL and parameter shape, including
JSONB serialization for entry_agent_scores. No real DB required.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from libs.storage.repositories.closed_trade_repo import ClosedTradeRepository


def _make_repo():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    return ClosedTradeRepository(db), db


class TestWriteClosedTrade:
    @pytest.mark.asyncio
    async def test_writes_with_full_payload(self):
        repo, db = _make_repo()
        position_id = uuid.uuid4()
        profile_id = uuid.uuid4()
        decision_event_id = uuid.uuid4()
        order_id = uuid.uuid4()
        opened_at = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        closed_at = datetime(2026, 4, 26, 13, 30, 0, tzinfo=timezone.utc)

        await repo.write_closed_trade(
            position_id=position_id,
            profile_id=profile_id,
            symbol="BTC/USDT",
            side="BUY",
            decision_event_id=decision_event_id,
            order_id=order_id,
            entry_price=Decimal("50000.00"),
            entry_quantity=Decimal("0.5"),
            entry_fee=Decimal("25.00"),
            entry_regime="TRENDING_UP",
            entry_agent_scores={"ta": 0.7, "sentiment": 0.3, "debate": 0.55},
            exit_price=Decimal("51000.00"),
            exit_fee=Decimal("25.50"),
            close_reason="take_profit",
            opened_at=opened_at,
            closed_at=closed_at,
            holding_duration_s=5400,
            realized_pnl=Decimal("449.50"),
            realized_pnl_pct=Decimal("0.018"),
            outcome="win",
        )

        db.execute.assert_awaited_once()
        sql, *args = db.execute.call_args.args
        assert "INSERT INTO closed_trades" in sql
        assert "ON CONFLICT (position_id) DO NOTHING" in sql
        assert args[0] == position_id
        assert args[1] == profile_id
        assert args[2] == "BTC/USDT"
        assert args[3] == "BUY"
        assert args[4] == decision_event_id
        assert args[5] == order_id
        assert args[6] == Decimal("50000.00")
        # entry_agent_scores serialized to JSON string
        assert isinstance(args[10], str)
        assert json.loads(args[10]) == {"ta": 0.7, "sentiment": 0.3, "debate": 0.55}
        assert args[13] == "take_profit"
        assert args[14] == opened_at
        assert args[15] == closed_at
        assert args[16] == 5400
        assert args[19] == "win"

    @pytest.mark.asyncio
    async def test_writes_with_null_optional_fields(self):
        """Decision event id, order id, regime, and agent scores may all be NULL."""
        repo, db = _make_repo()
        await repo.write_closed_trade(
            position_id=uuid.uuid4(),
            profile_id=uuid.uuid4(),
            symbol="ETH/USDT",
            side="SELL",
            decision_event_id=None,
            order_id=None,
            entry_price=Decimal("3000"),
            entry_quantity=Decimal("1"),
            entry_fee=Decimal("3"),
            entry_regime=None,
            entry_agent_scores=None,
            exit_price=Decimal("2900"),
            exit_fee=Decimal("2.9"),
            close_reason="stop_loss",
            opened_at=datetime.now(timezone.utc),
            closed_at=datetime.now(timezone.utc),
            holding_duration_s=120,
            realized_pnl=Decimal("-105.90"),
            realized_pnl_pct=Decimal("-0.0353"),
            outcome="loss",
        )
        db.execute.assert_awaited_once()
        _, *args = db.execute.call_args.args
        assert args[4] is None      # decision_event_id
        assert args[5] is None      # order_id
        assert args[9] is None      # entry_regime
        assert args[10] is None     # entry_agent_scores serializes None -> None

    @pytest.mark.asyncio
    async def test_decimal_in_agent_scores_serializes_to_float(self):
        """ML scores arriving as Decimal should be converted via the JSON encoder."""
        repo, db = _make_repo()
        await repo.write_closed_trade(
            position_id=uuid.uuid4(),
            profile_id=uuid.uuid4(),
            symbol="BTC/USDT",
            side="BUY",
            decision_event_id=None,
            order_id=None,
            entry_price=Decimal("100"),
            entry_quantity=Decimal("1"),
            entry_fee=Decimal("0"),
            entry_regime=None,
            entry_agent_scores={"ta": Decimal("0.7"), "debate": Decimal("0.55")},
            exit_price=Decimal("100"),
            exit_fee=Decimal("0"),
            close_reason="manual",
            opened_at=datetime.now(timezone.utc),
            closed_at=datetime.now(timezone.utc),
            holding_duration_s=10,
            realized_pnl=Decimal("0"),
            realized_pnl_pct=Decimal("0"),
            outcome="breakeven",
        )
        _, *args = db.execute.call_args.args
        decoded = json.loads(args[10])
        assert decoded == {"ta": 0.7, "debate": 0.55}


class TestQueries:
    @pytest.mark.asyncio
    async def test_get_recent_no_filters(self):
        repo, db = _make_repo()
        await repo.get_recent(limit=25)
        sql, *args = db.fetch.call_args.args
        assert "FROM closed_trades" in sql
        assert "ORDER BY closed_at DESC" in sql
        assert "WHERE" not in sql
        assert args == [25]

    @pytest.mark.asyncio
    async def test_get_recent_filters_symbol(self):
        repo, db = _make_repo()
        await repo.get_recent(symbol="BTC/USDT", limit=10)
        sql, *args = db.fetch.call_args.args
        assert "WHERE symbol = $1" in sql
        assert args[0] == "BTC/USDT"
        assert args[-1] == 10

    @pytest.mark.asyncio
    async def test_get_recent_filters_symbol_and_profile(self):
        repo, db = _make_repo()
        pid = uuid.uuid4()
        await repo.get_recent(symbol="ETH/USDT", profile_id=pid, limit=5)
        sql, *args = db.fetch.call_args.args
        assert "symbol = $1" in sql
        assert "profile_id = $2" in sql
        assert args[0] == "ETH/USDT"
        assert args[1] == pid
        assert args[-1] == 5

    @pytest.mark.asyncio
    async def test_get_by_position_returns_dict(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"position_id": "abc", "outcome": "win"})
        repo = ClosedTradeRepository(db)
        result = await repo.get_by_position(uuid.uuid4())
        assert result == {"position_id": "abc", "outcome": "win"}

    @pytest.mark.asyncio
    async def test_get_by_position_returns_none_when_missing(self):
        repo, _ = _make_repo()
        result = await repo.get_by_position(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_decision_event(self):
        repo, db = _make_repo()
        eid = uuid.uuid4()
        await repo.get_by_decision_event(eid)
        sql, *args = db.fetchrow.call_args.args
        assert "WHERE decision_event_id = $1" in sql
        assert args[0] == eid


class TestAggregateCloseReasons:
    @pytest.mark.asyncio
    async def test_no_filters_groups_by_close_reason_only(self):
        repo, db = _make_repo()
        await repo.aggregate_close_reasons(window_hours=24)
        sql, *args = db.fetch.call_args.args
        assert "GROUP BY close_reason" in sql
        assert "regime" not in sql.split("GROUP BY")[1]  # no regime grouping
        assert "AVG(realized_pnl_pct)" in sql
        assert "PERCENTILE_CONT(0.5)" in sql
        assert "FILTER (WHERE outcome = 'win')" in sql
        assert args[0] == "24"

    @pytest.mark.asyncio
    async def test_group_by_regime_adds_regime_column(self):
        repo, db = _make_repo()
        await repo.aggregate_close_reasons(window_hours=168, group_by_regime=True)
        sql, _ = db.fetch.call_args.args
        assert "COALESCE(entry_regime, 'unknown') AS regime" in sql
        assert "GROUP BY close_reason, COALESCE(entry_regime, 'unknown')" in sql

    @pytest.mark.asyncio
    async def test_filters_by_profile_symbol_regime(self):
        repo, db = _make_repo()
        pid = uuid.uuid4()
        await repo.aggregate_close_reasons(
            profile_id=pid,
            symbol="BTC/USDT",
            regime="TRENDING_UP",
            window_hours=72,
        )
        sql, *args = db.fetch.call_args.args
        assert "profile_id = $2" in sql
        assert "symbol = $3" in sql
        assert "COALESCE(entry_regime, 'unknown') = $4" in sql
        assert args == ["72", pid, "BTC/USDT", "TRENDING_UP"]

    @pytest.mark.asyncio
    async def test_post_processing_computes_win_rate_and_floats(self):
        from decimal import Decimal as D
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[
            {
                "close_reason": "stop_loss",
                "count": 19,
                "win_count": 0,
                "loss_count": 19,
                "breakeven_count": 0,
                "avg_pnl_pct": D("-0.096767"),
                "median_holding_s": 19009,
            },
            {
                "close_reason": "take_profit",
                "count": 14,
                "win_count": 14,
                "loss_count": 0,
                "breakeven_count": 0,
                "avg_pnl_pct": D("0.095932"),
                "median_holding_s": 149538,
            },
        ])
        repo = ClosedTradeRepository(db)
        out = await repo.aggregate_close_reasons()
        assert out[0]["win_rate"] == 0.0
        assert out[1]["win_rate"] == 1.0
        # Decimal converted to float for JSON serialisation
        assert isinstance(out[0]["avg_pnl_pct"], float)
        assert out[1]["avg_pnl_pct"] == pytest.approx(0.095932)

    @pytest.mark.asyncio
    async def test_empty_count_yields_null_win_rate(self):
        """Defensive: zero-count row (theoretical) shouldn't divide-by-zero."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[
            {
                "close_reason": "manual",
                "count": 0,
                "win_count": 0,
                "loss_count": 0,
                "breakeven_count": 0,
                "avg_pnl_pct": None,
                "median_holding_s": None,
            },
        ])
        repo = ClosedTradeRepository(db)
        out = await repo.aggregate_close_reasons()
        assert out[0]["win_rate"] is None
        assert out[0]["avg_pnl_pct"] is None


class TestAggregateAgentAttribution:
    @pytest.mark.asyncio
    async def test_query_buckets_each_agent_at_threshold(self):
        repo, db = _make_repo()
        await repo.aggregate_agent_attribution(window_hours=24, threshold=0.2)
        sql, *args = db.fetch.call_args.args
        # Threshold reused across the three CASE expressions via $2.
        assert "(d.agents#>>'{ta,score}')::FLOAT > $2" in sql
        assert "(d.agents#>>'{sentiment,score}')::FLOAT < -$2" in sql
        assert "(d.agents#>>'{debate,score}')::FLOAT > $2" in sql
        # Pattern composed from three buckets, ordered by count.
        assert "ta_bucket || '+' || sent_bucket || '+' || debate_bucket" in sql
        assert "ORDER BY count DESC" in sql
        # First two args are window_hours (string) and threshold (float).
        assert args[0] == "24"
        assert args[1] == 0.2

    @pytest.mark.asyncio
    async def test_inner_join_filters_to_trades_with_decision_link(self):
        repo, db = _make_repo()
        await repo.aggregate_agent_attribution()
        sql, _, _, _ = db.fetch.call_args.args
        assert "INNER JOIN trade_decisions d" in sql
        assert "d.event_id = ct.decision_event_id" in sql
        assert "d.outcome = 'APPROVED'" in sql

    @pytest.mark.asyncio
    async def test_filters_by_profile_and_symbol(self):
        repo, db = _make_repo()
        pid = uuid.uuid4()
        await repo.aggregate_agent_attribution(
            profile_id=pid,
            symbol="ETH/USDT",
            window_hours=72,
            threshold=0.1,
            limit=10,
        )
        sql, *args = db.fetch.call_args.args
        assert "ct.profile_id = $3" in sql
        assert "ct.symbol = $4" in sql
        # window, threshold, profile_id, symbol, limit
        assert args == ["72", 0.1, pid, "ETH/USDT", 10]

    @pytest.mark.asyncio
    async def test_post_processing_computes_win_rate_and_floats(self):
        from decimal import Decimal as D
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[
            {
                "pattern": "TA_BULL+SENT_BULL+DBT_BULL",
                "ta_bucket": "TA_BULL",
                "sent_bucket": "SENT_BULL",
                "debate_bucket": "DBT_BULL",
                "count": 8,
                "win_count": 6,
                "loss_count": 2,
                "breakeven_count": 0,
                "avg_pnl_pct": D("0.014321"),
                "avg_pnl_usd": D("12.5678"),
                "avg_confidence_lift": D("0.084500"),
            },
            {
                "pattern": "TA_BEAR+SENT_BULL+DBT_NEUTRAL",
                "ta_bucket": "TA_BEAR",
                "sent_bucket": "SENT_BULL",
                "debate_bucket": "DBT_NEUTRAL",
                "count": 2,
                "win_count": 0,
                "loss_count": 2,
                "breakeven_count": 0,
                "avg_pnl_pct": D("-0.002728"),
                "avg_pnl_usd": D("-12.11"),
                "avg_confidence_lift": D("0.0699"),
            },
        ])
        repo = ClosedTradeRepository(db)
        out = await repo.aggregate_agent_attribution()
        assert out[0]["win_rate"] == pytest.approx(0.75)
        assert out[1]["win_rate"] == 0.0
        assert isinstance(out[0]["avg_pnl_pct"], float)
        assert isinstance(out[0]["avg_pnl_usd"], float)
        assert isinstance(out[0]["avg_confidence_lift"], float)


class TestAggregateRuleHeatmap:
    @pytest.mark.asyncio
    async def test_query_unrolls_conditions_and_builds_canonical_fingerprint(self):
        repo, db = _make_repo()
        await repo.aggregate_rule_heatmap(window_hours=24, min_trades=2)
        sql, *args = db.fetch.call_args.args
        # The condition array is unrolled with jsonb_array_elements + LATERAL.
        assert "jsonb_array_elements(d.strategy->'conditions')" in sql
        # Fingerprint is built sorted so any condition order produces the
        # same fingerprint string.
        assert "ORDER BY indicator, operator, threshold" in sql
        assert "string_agg(" in sql
        assert "indicator || ':' || operator || ':' || threshold" in sql
        # min_trades is applied via HAVING so the filter happens after
        # aggregation rather than dropping individual decisions.
        assert "HAVING COUNT(*) >= $2" in sql
        assert args[0] == "24"
        assert args[1] == 2

    @pytest.mark.asyncio
    async def test_filters_by_profile_and_symbol(self):
        repo, db = _make_repo()
        pid = uuid.uuid4()
        await repo.aggregate_rule_heatmap(
            profile_id=pid,
            symbol="ETH/USDT",
            window_hours=72,
            min_trades=3,
            limit=20,
        )
        sql, *args = db.fetch.call_args.args
        assert "ct.profile_id = $3" in sql
        assert "ct.symbol = $4" in sql
        # window, min_trades, profile_id, symbol, limit
        assert args == ["72", 3, pid, "ETH/USDT", 20]

    @pytest.mark.asyncio
    async def test_post_processing_computes_win_rate_and_isoformat(self):
        from decimal import Decimal as D
        from datetime import datetime as dt, timezone as tz
        first = dt(2026, 5, 1, 10, 0, tzinfo=tz.utc)
        last = dt(2026, 5, 6, 16, 30, tzinfo=tz.utc)
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[
            {
                "fingerprint": "rsi:LT:50.0 | macd.histogram:GT:0.0",
                "trade_count": 4,
                "win_count": 3,
                "loss_count": 1,
                "breakeven_count": 0,
                "avg_pnl_pct": D("0.018500"),
                "avg_pnl_usd": D("18.50"),
                "first_trade_at": first,
                "last_trade_at": last,
            },
        ])
        repo = ClosedTradeRepository(db)
        out = await repo.aggregate_rule_heatmap()
        assert out[0]["win_rate"] == 0.75
        assert isinstance(out[0]["avg_pnl_pct"], float)
        assert isinstance(out[0]["avg_pnl_usd"], float)
        assert out[0]["first_trade_at"] == first.isoformat()
        assert out[0]["last_trade_at"] == last.isoformat()


class TestAggregateByAttribute:
    @pytest.mark.asyncio
    async def test_side_dimension_uses_raw_column(self):
        repo, db = _make_repo()
        await repo.aggregate_by_attribute(dimension="side", window_hours=24)
        sql, *args = db.fetch.call_args.args
        assert "ct.side AS bucket" in sql
        assert args[0] == "24"

    @pytest.mark.asyncio
    async def test_regime_dimension_coalesces_unknown(self):
        repo, db = _make_repo()
        await repo.aggregate_by_attribute(dimension="regime")
        sql = db.fetch.call_args.args[0]
        assert "COALESCE(ct.entry_regime, 'unknown')" in sql

    @pytest.mark.asyncio
    async def test_hold_duration_buckets(self):
        repo, db = _make_repo()
        await repo.aggregate_by_attribute(dimension="hold_duration")
        sql = db.fetch.call_args.args[0]
        assert "holding_duration_s < 3600" in sql
        assert "'< 1h'" in sql
        assert "'1–6h'" in sql        # en-dash matches the source
        assert "'≥ 24h'" in sql

    @pytest.mark.asyncio
    async def test_hour_dimension_uses_utc(self):
        repo, db = _make_repo()
        await repo.aggregate_by_attribute(dimension="hour")
        sql = db.fetch.call_args.args[0]
        assert "AT TIME ZONE 'UTC'" in sql
        assert "'morning (06–11 UTC)'" in sql

    @pytest.mark.asyncio
    async def test_day_of_week_uses_dow(self):
        repo, db = _make_repo()
        await repo.aggregate_by_attribute(dimension="day_of_week")
        sql = db.fetch.call_args.args[0]
        assert "EXTRACT(dow FROM ct.opened_at AT TIME ZONE 'UTC')" in sql
        assert "'Mon'" in sql
        assert "'Sun'" in sql

    @pytest.mark.asyncio
    async def test_unknown_dimension_raises(self):
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="Unknown dimension"):
            await repo.aggregate_by_attribute(dimension="garbage")

    @pytest.mark.asyncio
    async def test_filters_by_profile_and_symbol(self):
        repo, db = _make_repo()
        pid = uuid.uuid4()
        await repo.aggregate_by_attribute(
            dimension="side",
            profile_id=pid,
            symbol="BTC/USDT",
            window_hours=24,
            limit=10,
        )
        sql, *args = db.fetch.call_args.args
        assert "ct.profile_id = $2" in sql
        assert "ct.symbol = $3" in sql
        assert args == ["24", pid, "BTC/USDT", 10]

    @pytest.mark.asyncio
    async def test_post_processing_computes_win_rate(self):
        from decimal import Decimal as D
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[
            {
                "bucket": "BUY",
                "count": 10,
                "win_count": 7,
                "loss_count": 3,
                "breakeven_count": 0,
                "avg_pnl_pct": D("0.025"),
                "avg_pnl_usd": D("12.50"),
            },
        ])
        repo = ClosedTradeRepository(db)
        out = await repo.aggregate_by_attribute(dimension="side")
        assert out[0]["win_rate"] == 0.7
        assert isinstance(out[0]["avg_pnl_pct"], float)
        assert isinstance(out[0]["avg_pnl_usd"], float)

    @pytest.mark.parametrize(
        "dimension,fragment",
        [
            ("symbol", "ct.symbol AS bucket"),
            ("outcome", "ct.outcome AS bucket"),
            ("close_reason", "ct.close_reason AS bucket"),
        ],
    )
    @pytest.mark.asyncio
    async def test_new_dimensions_added(self, dimension, fragment):
        repo, db = _make_repo()
        await repo.aggregate_by_attribute(dimension=dimension)
        sql = db.fetch.call_args.args[0]
        assert fragment in sql
