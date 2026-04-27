"""Alert detectors for monitoring service metrics."""

from abc import ABC, abstractmethod
from typing import Optional
from app.alerts.models import (
    AlertEvent,
    AlertType,
    AlertSeverity,
    AlertStatus,
    AlertConfig,
)


class MetricsProvider:
    """Interface for accessing system metrics."""

    def get_average_latency(self) -> Optional[float]:
        """Get average request latency in seconds."""
        raise NotImplementedError

    def get_error_rate(self) -> Optional[float]:
        """Get error rate as a decimal (e.g., 0.05 for 5%)."""
        raise NotImplementedError

    def get_request_count_last_seconds(self, seconds: int = 30) -> int:
        """Get number of requests in the last N seconds."""
        raise NotImplementedError


class AlertDetector(ABC):
    """Abstract base class for alert detectors."""

    @abstractmethod
    def detect(self, metrics: MetricsProvider) -> Optional[AlertEvent]:
        """
        Detect if an alert condition is met.

        Args:
            metrics: The metrics provider

        Returns:
            AlertEvent if condition is met, None otherwise
        """


class LatencyDetector(AlertDetector):
    """Detector for high latency alerts."""

    def __init__(self, config: AlertConfig) -> None:
        """Initialize LatencyDetector."""
        self.config = config

    def detect(self, metrics: MetricsProvider) -> Optional[AlertEvent]:
        """
        Detect if average latency exceeds threshold.

        Args:
            metrics: The metrics provider

        Returns:
            AlertEvent if latency exceeds threshold, None otherwise
        """
        avg_latency = metrics.get_average_latency()

        if avg_latency is None or avg_latency <= self.config.latency_threshold:
            return None

        return AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message=(
                f"API latency exceeded {self.config.latency_threshold}s:"
                f" {avg_latency:.2f}s"
            ),
            status=AlertStatus.ACTIVE,
            context={
                "current_latency": avg_latency,
                "threshold": self.config.latency_threshold,
            },
        )


class ErrorRateDetector(AlertDetector):
    """Detector for high error rate alerts."""

    def __init__(self, config: AlertConfig) -> None:
        """Initialize ErrorRateDetector."""
        self.config = config

    def detect(self, metrics: MetricsProvider) -> Optional[AlertEvent]:
        """
        Detect if error rate exceeds threshold.

        Args:
            metrics: The metrics provider

        Returns:
            AlertEvent if error rate exceeds threshold, None otherwise
        """
        error_rate = metrics.get_error_rate()

        if error_rate is None or error_rate <= self.config.error_rate_threshold:
            return None

        return AlertEvent(
            alert_type=AlertType.ERROR_RATE,
            severity=AlertSeverity.MEDIUM,
            message=(
                f"Error rate exceeded {self.config.error_rate_threshold * 100:.1f}%:"
                f" {error_rate * 100:.2f}%"
            ),
            status=AlertStatus.ACTIVE,
            context={
                "current_error_rate": error_rate,
                "threshold": self.config.error_rate_threshold,
            },
        )


class ServiceDownDetector(AlertDetector):
    """Detector for service down alerts."""

    def __init__(self, config: AlertConfig) -> None:
        """Initialize ServiceDownDetector."""
        self.config = config

    def detect(self, metrics: MetricsProvider) -> Optional[AlertEvent]:
        """
        Detect if service is down (no requests for threshold seconds).

        Args:
            metrics: The metrics provider

        Returns:
            AlertEvent if service is down, None otherwise
        """
        request_count = metrics.get_request_count_last_seconds(
            self.config.service_down_threshold
        )

        if request_count > 0:
            return None

        return AlertEvent(
            alert_type=AlertType.SERVICE_DOWN,
            severity=AlertSeverity.CRITICAL,
            message=(
                f"Service appears to be down: no requests in last"
                f" {self.config.service_down_threshold}s"
            ),
            status=AlertStatus.ACTIVE,
            context={
                "downtime_threshold_seconds": self.config.service_down_threshold,
                "requests_in_window": request_count,
            },
        )
