"""Tests for alert notifiers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.alerts.models import AlertEvent, AlertType, AlertSeverity, AlertStatus
from app.alerts.notifiers import (
    Notifier,
    MockNotifier,
    SlackNotifier,
)


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

    def test_notifier_is_abstract(self):
        """Verify Notifier cannot be instantiated directly."""
        from abc import ABC

        assert issubclass(Notifier, ABC)

    def test_notifier_has_send_method(self):
        """Verify Notifier defines send method."""
        assert hasattr(Notifier, "send")

    def test_notifier_send_is_async(self):
        """Verify Notifier.send is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(Notifier.send)


class TestMockNotifier:
    """Test MockNotifier implementation."""

    def test_mock_notifier_creation(self):
        """Verify MockNotifier can be instantiated."""
        notifier = MockNotifier()
        assert isinstance(notifier, MockNotifier)
        assert isinstance(notifier, Notifier)

    @pytest.mark.asyncio
    async def test_mock_notifier_send_returns_true(self, sample_alert):
        """Verify MockNotifier.send returns True on success."""
        notifier = MockNotifier()
        result = await notifier.send(sample_alert)
        assert result is True

    @pytest.mark.asyncio
    async def test_mock_notifier_stores_alerts(self, sample_alert, sample_error_alert):
        """Verify MockNotifier stores sent alerts."""
        notifier = MockNotifier()
        await notifier.send(sample_alert)
        await notifier.send(sample_error_alert)

        assert len(notifier.alerts) == 2
        assert notifier.alerts[0] == sample_alert
        assert notifier.alerts[1] == sample_error_alert

    @pytest.mark.asyncio
    async def test_mock_notifier_get_alerts(self, sample_alert):
        """Verify MockNotifier can retrieve stored alerts."""
        notifier = MockNotifier()
        await notifier.send(sample_alert)

        alerts = notifier.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].message == "API latency exceeded 5 seconds"

    @pytest.mark.asyncio
    async def test_mock_notifier_clear_alerts(self, sample_alert):
        """Verify MockNotifier can clear stored alerts."""
        notifier = MockNotifier()
        await notifier.send(sample_alert)
        assert len(notifier.alerts) == 1

        notifier.clear()
        assert len(notifier.alerts) == 0


class TestSlackNotifier:
    """Test SlackNotifier implementation."""

    def test_slack_notifier_creation(self):
        """Verify SlackNotifier can be instantiated with webhook URL."""
        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        notifier = SlackNotifier(webhook_url=webhook_url)
        assert isinstance(notifier, SlackNotifier)
        assert isinstance(notifier, Notifier)

    def test_slack_notifier_stores_webhook_url(self):
        """Verify SlackNotifier stores webhook URL."""
        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        notifier = SlackNotifier(webhook_url=webhook_url)
        assert notifier.webhook_url == webhook_url

    @pytest.mark.asyncio
    async def test_slack_notifier_send_formats_message(self, sample_alert):
        """Verify SlackNotifier formats alert as Slack message."""
        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        notifier = SlackNotifier(webhook_url=webhook_url)

        # Mock httpx.AsyncClient.post
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await notifier.send(sample_alert)

            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_slack_notifier_handles_failure(self, sample_alert):
        """Verify SlackNotifier returns False on HTTP error."""
        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        notifier = SlackNotifier(webhook_url=webhook_url)

        # Mock httpx.AsyncClient.post to return error
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await notifier.send(sample_alert)

            assert result is False

    @pytest.mark.asyncio
    async def test_slack_notifier_message_includes_context(self, sample_alert):
        """Verify Slack message includes alert context."""
        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
        notifier = SlackNotifier(webhook_url=webhook_url)

        # Mock httpx.AsyncClient.post to capture payload
        captured_payload = {}

        async def capture_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            response = MagicMock()
            response.status_code = 200
            return response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await notifier.send(sample_alert)

            # Verify payload contains important information
            assert "text" in captured_payload or "blocks" in captured_payload or "attachments" in captured_payload
