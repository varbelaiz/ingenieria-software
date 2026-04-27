"""Tests for alert scheduler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.alerts.models import (
    AlertEvent,
    AlertType,
    AlertSeverity,
    AlertStatus,
    AlertConfig,
)
from app.alerts.scheduler import AlertScheduler


@pytest.fixture
def alert_config():
    """Create alert configuration."""
    return AlertConfig(
        latency_threshold=5.0,
        error_rate_threshold=0.05,
        service_down_threshold=30,
    )


@pytest.fixture
def mock_detector():
    """Create mock detector."""
    detector = MagicMock()
    return detector


@pytest.fixture
def mock_notifier():
    """Create mock notifier."""
    notifier = MagicMock()
    notifier.send = AsyncMock(return_value=True)
    return notifier


@pytest.fixture
def mock_metrics():
    """Create mock metrics."""
    metrics = MagicMock()
    return metrics


class TestAlertScheduler:
    """Test AlertScheduler implementation."""

    def test_scheduler_creation(self, alert_config, mock_notifier):
        """Verify AlertScheduler can be instantiated."""
        detectors = []
        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=detectors,
        )
        assert isinstance(scheduler, AlertScheduler)

    def test_scheduler_stores_dependencies(self, alert_config, mock_notifier):
        """Verify AlertScheduler stores config, notifier, and detectors."""
        detectors = []
        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=detectors,
        )
        assert scheduler.config == alert_config
        assert scheduler.notifier == mock_notifier
        assert scheduler.detectors == detectors

    @pytest.mark.asyncio
    async def test_scheduler_check_alerts_executes_detectors(
        self, alert_config, mock_notifier, mock_metrics
    ):
        """Verify check_alerts executes all detectors."""
        detector1 = MagicMock()
        detector1.detect.return_value = None
        detector2 = MagicMock()
        detector2.detect.return_value = None

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[detector1, detector2],
        )

        await scheduler.check_alerts(mock_metrics)

        # Verify detectors were called
        detector1.detect.assert_called_once_with(mock_metrics)
        detector2.detect.assert_called_once_with(mock_metrics)

    @pytest.mark.asyncio
    async def test_scheduler_sends_alert_if_detector_triggers(
        self, alert_config, mock_notifier, mock_metrics
    ):
        """Verify alert is sent if detector returns alert."""
        alert = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Latency high",
            status=AlertStatus.ACTIVE,
        )

        detector = MagicMock()
        detector.detect.return_value = alert

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[detector],
        )

        await scheduler.check_alerts(mock_metrics)

        # Verify notifier was called with alert
        mock_notifier.send.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_scheduler_deduplicates_alerts(
        self, alert_config, mock_notifier, mock_metrics
    ):
        """Verify scheduler deduplicates alerts using deduplicator."""
        alert = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Latency high",
            status=AlertStatus.ACTIVE,
        )

        detector = MagicMock()
        detector.detect.return_value = alert

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[detector],
        )

        # First check - alert should be sent
        await scheduler.check_alerts(mock_metrics)
        assert mock_notifier.send.call_count == 1

        # Second check - alert should be deduped (not sent)
        await scheduler.check_alerts(mock_metrics)
        assert mock_notifier.send.call_count == 1  # Still 1, not 2

    @pytest.mark.asyncio
    async def test_scheduler_does_not_send_if_detector_returns_none(
        self, alert_config, mock_notifier, mock_metrics
    ):
        """Verify no alert is sent if detector returns None."""
        detector = MagicMock()
        detector.detect.return_value = None

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[detector],
        )

        await scheduler.check_alerts(mock_metrics)

        # Verify notifier was not called
        mock_notifier.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_scheduler_continues_if_one_detector_fails(
        self, alert_config, mock_notifier, mock_metrics
    ):
        """Verify scheduler continues if one detector raises exception."""
        alert = AlertEvent(
            alert_type=AlertType.ERROR_RATE,
            severity=AlertSeverity.MEDIUM,
            message="Error rate high",
            status=AlertStatus.ACTIVE,
        )

        detector1 = MagicMock()
        detector1.detect.side_effect = Exception("Detector error")

        detector2 = MagicMock()
        detector2.detect.return_value = alert

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[detector1, detector2],
        )

        # Should not raise exception
        await scheduler.check_alerts(mock_metrics)

        # Second detector should still be called
        detector2.detect.assert_called_once()

        # Alert from second detector should be sent
        mock_notifier.send.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_scheduler_handles_notifier_failure(
        self, alert_config, mock_notifier, mock_metrics
    ):
        """Verify scheduler handles notifier failure gracefully."""
        alert = AlertEvent(
            alert_type=AlertType.SERVICE_DOWN,
            severity=AlertSeverity.CRITICAL,
            message="Service down",
            status=AlertStatus.ACTIVE,
        )

        detector = MagicMock()
        detector.detect.return_value = alert

        mock_notifier.send.side_effect = Exception("Slack error")

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[detector],
        )

        # Should not raise exception
        await scheduler.check_alerts(mock_metrics)

        # Notifier should have been called
        mock_notifier.send.assert_called_once()

    def test_scheduler_has_check_alerts_async_method(self, alert_config, mock_notifier):
        """Verify check_alerts is an async method."""
        import inspect

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[],
        )
        assert inspect.iscoroutinefunction(scheduler.check_alerts)

    @pytest.mark.asyncio
    async def test_scheduler_multiple_detectors_trigger(
        self, alert_config, mock_notifier, mock_metrics
    ):
        """Verify scheduler sends multiple alerts from different detectors."""
        alert1 = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Latency high",
            status=AlertStatus.ACTIVE,
        )
        alert2 = AlertEvent(
            alert_type=AlertType.ERROR_RATE,
            severity=AlertSeverity.MEDIUM,
            message="Error rate high",
            status=AlertStatus.ACTIVE,
        )

        detector1 = MagicMock()
        detector1.detect.return_value = alert1

        detector2 = MagicMock()
        detector2.detect.return_value = alert2

        scheduler = AlertScheduler(
            config=alert_config,
            notifier=mock_notifier,
            detectors=[detector1, detector2],
        )

        await scheduler.check_alerts(mock_metrics)

        # Both alerts should be sent
        assert mock_notifier.send.call_count == 2
