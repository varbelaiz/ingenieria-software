"""Tests for alert detectors."""

import pytest
from unittest.mock import MagicMock, patch
from app.alerts.models import AlertEvent, AlertType, AlertSeverity, AlertStatus
from app.alerts.detectors import (
    AlertDetector,
    LatencyDetector,
    ErrorRateDetector,
    ServiceDownDetector,
)


@pytest.fixture
def mock_metrics():
    """Create a mock metrics object."""
    metrics = MagicMock()
    return metrics


class TestAlertDetectorInterface:
    """Test the AlertDetector abstract base class."""

    def test_detector_is_abstract(self):
        """Verify AlertDetector cannot be instantiated directly."""
        from abc import ABC

        assert issubclass(AlertDetector, ABC)

    def test_detector_has_detect_method(self):
        """Verify AlertDetector defines detect method."""
        assert hasattr(AlertDetector, "detect")


class TestLatencyDetector:
    """Test LatencyDetector implementation."""

    def test_latency_detector_creation(self):
        """Verify LatencyDetector can be instantiated."""
        config = MagicMock()
        config.latency_threshold = 5.0
        detector = LatencyDetector(config=config)
        assert isinstance(detector, LatencyDetector)
        assert isinstance(detector, AlertDetector)

    def test_latency_detector_stores_config(self):
        """Verify LatencyDetector stores configuration."""
        config = MagicMock()
        config.latency_threshold = 5.0
        detector = LatencyDetector(config=config)
        assert detector.config == config

    def test_latency_detector_no_alert_below_threshold(self, mock_metrics):
        """Verify no alert when latency is below threshold."""
        config = MagicMock()
        config.latency_threshold = 5.0
        detector = LatencyDetector(config=config)

        mock_metrics.get_average_latency.return_value = 3.5

        alert = detector.detect(mock_metrics)
        assert alert is None

    def test_latency_detector_alert_above_threshold(self, mock_metrics):
        """Verify alert triggered when latency exceeds threshold."""
        config = MagicMock()
        config.latency_threshold = 5.0
        detector = LatencyDetector(config=config)

        mock_metrics.get_average_latency.return_value = 6.5

        alert = detector.detect(mock_metrics)
        assert alert is not None
        assert isinstance(alert, AlertEvent)
        assert alert.alert_type == AlertType.LATENCY
        assert alert.severity == AlertSeverity.HIGH

    def test_latency_detector_alert_at_boundary(self, mock_metrics):
        """Verify alert behavior at exact threshold boundary."""
        config = MagicMock()
        config.latency_threshold = 5.0
        detector = LatencyDetector(config=config)

        mock_metrics.get_average_latency.return_value = 5.0

        # At threshold should NOT trigger (> not >=)
        alert = detector.detect(mock_metrics)
        assert alert is None

        # Slightly above threshold should trigger
        mock_metrics.get_average_latency.return_value = 5.001
        alert = detector.detect(mock_metrics)
        assert alert is not None

    def test_latency_detector_includes_context(self, mock_metrics):
        """Verify alert includes current latency and threshold in context."""
        config = MagicMock()
        config.latency_threshold = 5.0
        detector = LatencyDetector(config=config)

        mock_metrics.get_average_latency.return_value = 7.2

        alert = detector.detect(mock_metrics)
        assert alert.context is not None
        assert alert.context["current_latency"] == 7.2
        assert alert.context["threshold"] == 5.0


class TestErrorRateDetector:
    """Test ErrorRateDetector implementation."""

    def test_error_rate_detector_creation(self):
        """Verify ErrorRateDetector can be instantiated."""
        config = MagicMock()
        config.error_rate_threshold = 0.05
        detector = ErrorRateDetector(config=config)
        assert isinstance(detector, ErrorRateDetector)
        assert isinstance(detector, AlertDetector)

    def test_error_rate_detector_no_alert_below_threshold(self, mock_metrics):
        """Verify no alert when error rate is below threshold."""
        config = MagicMock()
        config.error_rate_threshold = 0.05
        detector = ErrorRateDetector(config=config)

        mock_metrics.get_error_rate.return_value = 0.02  # 2%

        alert = detector.detect(mock_metrics)
        assert alert is None

    def test_error_rate_detector_alert_above_threshold(self, mock_metrics):
        """Verify alert triggered when error rate exceeds threshold."""
        config = MagicMock()
        config.error_rate_threshold = 0.05
        detector = ErrorRateDetector(config=config)

        mock_metrics.get_error_rate.return_value = 0.08  # 8%

        alert = detector.detect(mock_metrics)
        assert alert is not None
        assert isinstance(alert, AlertEvent)
        assert alert.alert_type == AlertType.ERROR_RATE
        assert alert.severity == AlertSeverity.MEDIUM

    def test_error_rate_detector_no_alert_without_data(self, mock_metrics):
        """Verify no alert when insufficient data to calculate error rate."""
        config = MagicMock()
        config.error_rate_threshold = 0.05
        detector = ErrorRateDetector(config=config)

        mock_metrics.get_error_rate.return_value = None

        alert = detector.detect(mock_metrics)
        assert alert is None

    def test_error_rate_detector_includes_context(self, mock_metrics):
        """Verify alert includes current error rate and threshold in context."""
        config = MagicMock()
        config.error_rate_threshold = 0.05
        detector = ErrorRateDetector(config=config)

        mock_metrics.get_error_rate.return_value = 0.12  # 12%

        alert = detector.detect(mock_metrics)
        assert alert.context is not None
        assert alert.context["current_error_rate"] == 0.12
        assert alert.context["threshold"] == 0.05


class TestServiceDownDetector:
    """Test ServiceDownDetector implementation."""

    def test_service_down_detector_creation(self):
        """Verify ServiceDownDetector can be instantiated."""
        config = MagicMock()
        config.service_down_threshold = 30
        detector = ServiceDownDetector(config=config)
        assert isinstance(detector, ServiceDownDetector)
        assert isinstance(detector, AlertDetector)

    def test_service_down_detector_no_alert_with_requests(self, mock_metrics):
        """Verify no alert when service is receiving requests."""
        config = MagicMock()
        config.service_down_threshold = 30
        detector = ServiceDownDetector(config=config)

        mock_metrics.get_request_count_last_seconds.return_value = 5

        alert = detector.detect(mock_metrics)
        assert alert is None

    def test_service_down_detector_alert_no_requests(self, mock_metrics):
        """Verify alert when service has no requests for threshold seconds."""
        config = MagicMock()
        config.service_down_threshold = 30
        detector = ServiceDownDetector(config=config)

        mock_metrics.get_request_count_last_seconds.return_value = 0

        alert = detector.detect(mock_metrics)
        assert alert is not None
        assert isinstance(alert, AlertEvent)
        assert alert.alert_type == AlertType.SERVICE_DOWN
        assert alert.severity == AlertSeverity.CRITICAL

    def test_service_down_detector_critical_severity(self, mock_metrics):
        """Verify SERVICE_DOWN alert has CRITICAL severity."""
        config = MagicMock()
        config.service_down_threshold = 30
        detector = ServiceDownDetector(config=config)

        mock_metrics.get_request_count_last_seconds.return_value = 0

        alert = detector.detect(mock_metrics)
        assert alert.severity == AlertSeverity.CRITICAL

    def test_service_down_detector_includes_context(self, mock_metrics):
        """Verify alert includes downtime threshold in context."""
        config = MagicMock()
        config.service_down_threshold = 30
        detector = ServiceDownDetector(config=config)

        mock_metrics.get_request_count_last_seconds.return_value = 0

        alert = detector.detect(mock_metrics)
        assert alert.context is not None
        assert alert.context["downtime_threshold_seconds"] == 30
