"""Tests for Logger service: alerter dispatch to PagerDuty and Slack."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import msgpack
import pytest

from libs.core.enums import EventType
from libs.core.schemas import AlertEvent
from libs.messaging._serialisation import encode_event
from libs.messaging.channels import PUBSUB_SYSTEM_ALERTS
from services.logger.src.alerter import Alerter
from services.logger.src.event_subscriber import EventSubscriber

# ---------------------------------------------------------------------------
# Alerter tests
# ---------------------------------------------------------------------------


class TestAlerter:
    def _make_event(
        self,
        event_type="ORDER_REJECTED",
        profile_id="prof-1",
        timestamp_us=1000000,
        reason="Risk limit exceeded",
    ):
        return SimpleNamespace(
            event_type=event_type,
            profile_id=profile_id,
            timestamp_us=timestamp_us,
            reason=reason,
        )

    @pytest.mark.asyncio
    async def test_send_alert_no_channels_logs_locally(self):
        alerter = Alerter()
        event = self._make_event()
        # Should not raise when no channels configured
        await alerter.send_alert(event)

    @pytest.mark.asyncio
    async def test_send_alert_pagerduty(self):
        alerter = Alerter(pagerduty_key="test-routing-key")
        event = self._make_event(event_type="ALERT_RED")

        with patch("services.logger.src.alerter.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=202))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await alerter.send_alert(event)
            mock_client.post.assert_called_once()
            call_url = mock_client.post.call_args[0][0]
            assert "pagerduty.com" in call_url

    @pytest.mark.asyncio
    async def test_send_alert_slack(self):
        alerter = Alerter(slack_webhook="https://hooks.slack.com/test")
        event = self._make_event()

        with patch("services.logger.src.alerter.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await alerter.send_alert(event)
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_both_channels(self):
        alerter = Alerter(
            pagerduty_key="key", slack_webhook="https://hooks.slack.com/test"
        )
        event = self._make_event()

        with patch("services.logger.src.alerter.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await alerter.send_alert(event)
            assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_pagerduty_severity_red_is_critical(self):
        alerter = Alerter(pagerduty_key="key")
        event = self._make_event(event_type="ALERT_RED")

        with patch("services.logger.src.alerter.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=202))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await alerter.send_alert(event)
            call_kwargs = mock_client.post.call_args
            pd_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert pd_payload["payload"]["severity"] == "critical"


# ---------------------------------------------------------------------------
# EventSubscriber._on_alert tests (registry row 46 + the pubsub crash-loop)
# ---------------------------------------------------------------------------


def _make_subscriber():
    audit_repo = AsyncMock()
    alerter = AsyncMock()
    es = EventSubscriber(
        consumer=MagicMock(),
        pubsub=MagicMock(),
        audit_repo=audit_repo,
        alerter=alerter,
        subscriber=MagicMock(),
    )
    return es, audit_repo, alerter


def _alert_event(level="RED", message="Reconciliation drift on BTC/USDT", **kw):
    return AlertEvent(
        event_type=kw.pop("event_type", EventType.ALERT_RED),
        timestamp_us=kw.pop("timestamp_us", 1_700_000_000_000_000),
        source_service=kw.pop("source_service", "execution"),
        message=message,
        level=level,
        **kw,
    )


class TestEventSubscriberOnAlert:
    @pytest.mark.asyncio
    async def test_red_alert_dispatches_real_alertevent_fields(self):
        """Row 46: the re-dispatched alert carries the REAL alert text and
        profile, not 'Unknown Alert'/'GLOBAL' from non-existent keys."""
        es, audit_repo, alerter = _make_subscriber()
        pid = str(uuid.uuid4())
        ev = _alert_event(profile_id=pid)

        await es._on_alert(encode_event(ev))

        alerter.send_alert.assert_awaited_once()
        sent = alerter.send_alert.await_args.args[0]
        # Mirror the Alerter's own field resolution:
        assert (
            getattr(sent, "reason", getattr(sent, "message", None))
            == "Reconciliation drift on BTC/USDT"
        )
        assert sent.profile_id == pid
        assert sent.source_service == "execution"

    @pytest.mark.asyncio
    async def test_audit_write_receives_real_event_not_dict(self):
        """The crash-loop bug: write_audit_event reads event.event_id /
        event.event_type.value / event.source_service / event.timestamp_us —
        a raw dict crashed the whole pubsub loop on EVERY alert."""
        es, audit_repo, alerter = _make_subscriber()
        ev = _alert_event()

        await es._on_alert(encode_event(ev))

        audit_repo.write_audit_event.assert_awaited_once()
        written, payload = audit_repo.write_audit_event.await_args.args
        # Replicate the exact attribute accesses AuditRepository performs:
        assert written.event_id == ev.event_id
        assert written.event_type.value == "ALERT_RED"
        assert written.source_service == "execution"
        assert written.timestamp_us == ev.timestamp_us
        assert payload["channel"] == PUBSUB_SYSTEM_ALERTS
        assert payload["message"] == ev.message

    @pytest.mark.asyncio
    async def test_non_red_is_audited_but_not_alerted(self):
        es, audit_repo, alerter = _make_subscriber()
        ev = _alert_event(level="AMBER", event_type=EventType.ALERT_AMBER)

        await es._on_alert(encode_event(ev))

        alerter.send_alert.assert_not_awaited()
        audit_repo.write_audit_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uuid_profile_id_passes_to_audit_column(self):
        es, audit_repo, _ = _make_subscriber()
        pid = str(uuid.uuid4())
        await es._on_alert(encode_event(_alert_event(profile_id=pid)))
        _, payload = audit_repo.write_audit_event.await_args.args
        assert payload["profile_id"] == pid

    @pytest.mark.asyncio
    async def test_non_uuid_profile_id_kept_out_of_uuid_column(self):
        """audit_log.profile_id is a UUID column — sentinel strings must not
        reach it (would 500 the insert), but stay visible in the payload."""
        es, audit_repo, _ = _make_subscriber()
        await es._on_alert(encode_event(_alert_event(profile_id="GLOBAL")))
        _, payload = audit_repo.write_audit_event.await_args.args
        assert "profile_id" not in payload
        assert payload["alert_profile_id"] == "GLOBAL"

    @pytest.mark.asyncio
    async def test_legacy_dict_payload_degrades_to_synthesised_event(self):
        """A bare msgpack dict (no __type__) must not crash the loop; the
        fallback synthesises an AlertEvent from whatever fields exist."""
        es, audit_repo, alerter = _make_subscriber()
        raw = msgpack.packb(
            {"level": "RED", "reason": "Legacy alert text", "profile_id": "GLOBAL"},
            use_bin_type=True,
        )

        await es._on_alert(raw)

        alerter.send_alert.assert_awaited_once()
        sent = alerter.send_alert.await_args.args[0]
        assert sent.message == "Legacy alert text"
        written, _ = audit_repo.write_audit_event.await_args.args
        assert written.event_id is not None  # real event, not a dict

    @pytest.mark.asyncio
    async def test_garbage_bytes_are_skipped_without_raising(self):
        es, audit_repo, alerter = _make_subscriber()
        await es._on_alert(b"\x00\x01 not msgpack \xff")
        alerter.send_alert.assert_not_awaited()
        audit_repo.write_audit_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_propagate(self):
        """A transient DB blip on the audit write must not kill (and
        therefore crash-loop) the pubsub subscription."""
        es, audit_repo, _ = _make_subscriber()
        audit_repo.write_audit_event.side_effect = TimeoutError("db blip")
        await es._on_alert(encode_event(_alert_event(level="INFO")))  # no raise

    @pytest.mark.asyncio
    async def test_run_pubsub_subscribes_handler_on_system_alerts(self):
        es, _, _ = _make_subscriber()
        es.subscriber.subscribe = AsyncMock()
        await es.run_pubsub()
        es.subscriber.subscribe.assert_awaited_once_with(
            PUBSUB_SYSTEM_ALERTS, es._on_alert
        )
