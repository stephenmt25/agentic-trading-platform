import time
from decimal import Decimal

from libs.core.schemas import PnlUpdateEvent


def test_pnl_schema_contract():
    """Round-trip the full FE-W2 wire contract: per-position identity plus the
    fee/tax breakdown, with every financial field a Decimal (never float)."""

    ev = PnlUpdateEvent(
        profile_id="p-100",
        position_id="pos-x",
        symbol="ETH/USD",
        gross_pnl=Decimal("153.00"),
        net_pnl=Decimal("150.00"),  # historical semantics: PRE-tax net
        fees=Decimal("3.00"),
        net_pre_tax=Decimal("150.00"),
        net_post_tax=Decimal("120.50"),
        tax_estimate=Decimal("29.50"),
        pct_return=Decimal("0.15"),
        timestamp_us=int(time.time() * 1000000),
        source_service="pnl",
    )

    enc = ev.model_dump_json()
    dec = PnlUpdateEvent.model_validate_json(enc)

    assert dec.profile_id == "p-100"
    assert dec.position_id == "pos-x"
    assert dec.net_pnl == dec.net_pre_tax
    assert dec.net_post_tax == Decimal("120.50")
    assert dec.pct_return == Decimal("0.15")
    for value in (
        dec.gross_pnl,
        dec.net_pnl,
        dec.fees,
        dec.net_pre_tax,
        dec.net_post_tax,
        dec.tax_estimate,
        dec.pct_return,
    ):
        assert isinstance(value, Decimal)


def test_pnl_schema_accepts_legacy_payloads():
    """Payloads predating 2026-06 (no position_id / breakdown fields) must
    still validate — the new fields are Optional."""

    legacy = PnlUpdateEvent(
        profile_id="p-100",
        symbol="ETH/USD",
        gross_pnl=Decimal("10.00"),
        net_pnl=Decimal("9.50"),
        pct_return=Decimal("0.01"),
        timestamp_us=int(time.time() * 1000000),
        source_service="pnl",
    )

    assert legacy.position_id is None
    assert legacy.fees is None
    assert legacy.net_pre_tax is None
    assert legacy.net_post_tax is None
    assert legacy.tax_estimate is None
