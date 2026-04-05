"""Tests for Logger service: alerter dispatch to PagerDuty and Slack."""

from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import pytest

from services.logger.src.alerter import Alerter


# ---------------------------------------------------------------------------
# Alerter tests
# ---------------------------------------------------------------------------

class TestAlerter:
    def _make_event(self, event_type="ORDER_REJECTED", profile_id="prof-1",
                    timestamp_us=1000000, reason="Risk limit exceeded"):
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
        alerter = Alerter(pagerduty_key="key", slack_webhook="https://hooks.slack.com/test")
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
