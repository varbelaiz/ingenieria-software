"""Tests for alert notifiers."""

import inspect
from abc import ABC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.alerts.models import AlertEvent, AlertSeverity, AlertStatus, AlertType
from app.alerts.notifiers import (
    MockNotifier,
    Notifier,
    SlackNotifier,
)

_WEBHOOK = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"


@pytest.fixture
def sample_alert() -> AlertEvent:
    """Create a sample alert event for testing."""
    return AlertEvent(
        alert_type=AlertType.LATENCY,
        severity=AlertSeverity.HIGH,
        message="API latency exceeded 5 seconds",
        status=AlertStatus.ACTIVE,
        context={"current_latency": 6.5, "threshold": 5.0},
    )


@pytest.fixture
def sample_error_alert() -> AlertEvent:
    """Create a sample error rate alert."""
    return AlertEvent(
        alert_type=AlertType.ERROR_RATE,
        severity=AlertSeverity.MEDIUM,
        message="Error rate exceeds 5%",
        status=AlertStatus.ACTIVE,
        context={"current_error_rate": 0.08, "threshold": 0.05},
    )


class TestNotifierInterface:
    """Test the Notifier abstract base class."""

    def test_notifier_is_abstract(self) -> None:
        """Verify Notifier cannot be instantiated directly."""
        assert issubclass(Notifier, ABC)

    def test_notifier_has_send_method(self) -> None:
        """Verify Notifier defines send method."""
        assert hasattr(Notifier, "send")

    def test_notifier_send_is_async(self) -> None:
        """Verify Notifier.send is an async method."""
        assert inspect.iscoroutinefunction(Notifier.send)


class TestMockNotifier:
    """Test MockNotifier implementation."""

    def test_mock_notifier_creation(self) -> None:
        """Verify MockNotifier can be instantiated."""
        notifier = MockNotifier()
        assert isinstance(notifier, MockNotifier)
        assert isinstance(notifier, Notifier)

    @pytest.mark.asyncio
    async def test_mock_notifier_send_returns_true(
        self, sample_alert: AlertEvent
    ) -> None:
        """Verify MockNotifier.send returns True on success."""
        notifier = MockNotifier()
        result = await notifier.send(sample_alert)
        assert result is True

    @pytest.mark.asyncio
    async def test_mock_notifier_stores_alerts(
        self, sample_alert: AlertEvent, sample_error_alert: AlertEvent
    ) -> None:
        """Verify MockNotifier stores sent alerts."""
        notifier = MockNotifier()
        await notifier.send(sample_alert)
        await notifier.send(sample_error_alert)

        assert len(notifier.alerts) == 2
        assert notifier.alerts[0] == sample_alert
        assert notifier.alerts[1] == sample_error_alert

    @pytest.mark.asyncio
    async def test_mock_notifier_get_alerts(self, sample_alert: AlertEvent) -> None:
        """Verify MockNotifier can retrieve stored alerts."""
        notifier = MockNotifier()
        await notifier.send(sample_alert)

        alerts = notifier.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].message == "API latency exceeded 5 seconds"

    @pytest.mark.asyncio
    async def test_mock_notifier_clear_alerts(self, sample_alert: AlertEvent) -> None:
        """Verify MockNotifier can clear stored alerts."""
        notifier = MockNotifier()
        await notifier.send(sample_alert)
        assert len(notifier.alerts) == 1

        notifier.clear()
        assert len(notifier.alerts) == 0


class TestSlackNotifier:
    """Test SlackNotifier implementation."""

    def test_slack_notifier_creation(self) -> None:
        """Verify SlackNotifier can be instantiated with webhook URL."""
        notifier = SlackNotifier(webhook_url=_WEBHOOK)
        assert isinstance(notifier, SlackNotifier)
        assert isinstance(notifier, Notifier)

    def test_slack_notifier_stores_webhook_url(self) -> None:
        """Verify SlackNotifier stores webhook URL."""
        notifier = SlackNotifier(webhook_url=_WEBHOOK)
        assert notifier.webhook_url == _WEBHOOK

    @pytest.mark.asyncio
    async def test_slack_notifier_send_formats_message(
        self, sample_alert: AlertEvent
    ) -> None:
        """Verify SlackNotifier formats alert as Slack message."""
        notifier = SlackNotifier(webhook_url=_WEBHOOK)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await notifier.send(sample_alert)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_slack_notifier_handles_failure(
        self, sample_alert: AlertEvent
    ) -> None:
        """Verify SlackNotifier returns False on HTTP error."""
        notifier = SlackNotifier(webhook_url=_WEBHOOK)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await notifier.send(sample_alert)

        assert result is False

    @pytest.mark.asyncio
    async def test_slack_notifier_message_includes_context(
        self, sample_alert: AlertEvent
    ) -> None:
        """Verify Slack message includes alert context."""
        notifier = SlackNotifier(webhook_url=_WEBHOOK)

        captured_payload: dict[str, Any] = {}

        async def capture_post(
            _url: str, json: dict[str, Any] | None = None, **_: Any
        ) -> MagicMock:
            captured_payload.update(json or {})
            response = MagicMock()
            response.status_code = 200
            return response

        mock_client = MagicMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = capture_post

        with patch("httpx.AsyncClient", return_value=mock_client):
            await notifier.send(sample_alert)

        assert (
            "text" in captured_payload
            or "blocks" in captured_payload
            or "attachments" in captured_payload
        )
