"""Unit tests for OrderApprovedEvent.decision_event_id round-trip.

Validates the new correlation field added in PR1 Step 2:
- Constructs cleanly with and without decision_event_id
- Survives Pydantic JSON serialization round-trip (proxy for Redis Streams transport)
- Default value is None when omitted
"""

import json
import uuid
from decimal import Decimal

import pytest

from libs.core.enums import OrderSide
from libs.core.schemas import OrderApprovedEvent


def _make(decision_event_id=None):
    return OrderApprovedEvent(
        profile_id="test-profile-001",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        price=Decimal("50000"),
        decision_event_id=decision_event_id,
        timestamp_us=1_700_000_000_000_000,
        source_service="test",
    )


class TestOrderApprovedEventDecisionLink:
    def test_default_is_none(self):
        ev = OrderApprovedEvent(
            profile_id="p",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("100"),
            timestamp_us=0,
            source_service="test",
        )
        assert ev.decision_event_id is None

    def test_accepts_uuid(self):
        eid = uuid.uuid4()
        ev = _make(decision_event_id=eid)
        assert ev.decision_event_id == eid

    def test_json_roundtrip_preserves_uuid(self):
        eid = uuid.uuid4()
        ev = _make(decision_event_id=eid)
        # Pydantic V2 model_dump_json serializes UUID to string
        payload = ev.model_dump_json()
        decoded = json.loads(payload)
        assert decoded["decision_event_id"] == str(eid)

        # Re-deserialize and confirm UUID type round-trips
        ev2 = OrderApprovedEvent.model_validate_json(payload)
        assert ev2.decision_event_id == eid

    def test_json_roundtrip_with_null(self):
        ev = _make(decision_event_id=None)
        payload = ev.model_dump_json()
        decoded = json.loads(payload)
        assert decoded["decision_event_id"] is None

        ev2 = OrderApprovedEvent.model_validate_json(payload)
        assert ev2.decision_event_id is None

    def test_legacy_payload_without_field_deserializes(self):
        """Old in-flight messages (pre-PR1) lack the field — must still parse."""
        legacy = {
            "profile_id": "test-profile-001",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "quantity": "0.5",
            "price": "50000",
            "timestamp_us": 1_700_000_000_000_000,
            "source_service": "test",
        }
        ev = OrderApprovedEvent.model_validate(legacy)
        assert ev.decision_event_id is None
