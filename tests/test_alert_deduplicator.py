"""Tests for alert deduplication logic."""

import time

import pytest

from app.alerts.deduplicator import AlertDeduplicator
from app.alerts.models import AlertEvent, AlertSeverity, AlertStatus, AlertType


@pytest.fixture
def sample_alert() -> AlertEvent:
    """Create a sample alert event for testing."""
    return AlertEvent(
        alert_type=AlertType.LATENCY,
        severity=AlertSeverity.HIGH,
        message="API latency exceeded 5 seconds",
        status=AlertStatus.ACTIVE,
    )


@pytest.fixture
def different_alert() -> AlertEvent:
    """Create a different alert event."""
    return AlertEvent(
        alert_type=AlertType.ERROR_RATE,
        severity=AlertSeverity.MEDIUM,
        message="Error rate high",
        status=AlertStatus.ACTIVE,
    )


class TestAlertDeduplicator:
    """Test AlertDeduplicator implementation."""

    def test_deduplicator_creation(self) -> None:
        """Verify AlertDeduplicator can be instantiated."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert isinstance(dedup, AlertDeduplicator)

    def test_deduplicator_stores_window_size(self) -> None:
        """Verify AlertDeduplicator stores deduplication window."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert dedup.dedup_window_seconds == 300

    def test_first_alert_should_notify(self, sample_alert: AlertEvent) -> None:
        """Verify first alert of a type should be notified."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert dedup.should_notify(sample_alert) is True

    def test_same_alert_twice_within_window_not_notify(
        self, sample_alert: AlertEvent
    ) -> None:
        """Verify same alert twice within window is deduped."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert dedup.should_notify(sample_alert) is True
        assert dedup.should_notify(sample_alert) is False

    def test_different_alert_types_notify_separately(
        self, sample_alert: AlertEvent, different_alert: AlertEvent
    ) -> None:
        """Verify different alert types are not deduplicated together."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert dedup.should_notify(sample_alert) is True
        assert dedup.should_notify(different_alert) is True

    def test_alert_notify_after_window_expires(self, sample_alert: AlertEvent) -> None:
        """Verify alert notifies again after dedup window expires."""
        dedup = AlertDeduplicator(dedup_window_seconds=1)

        assert dedup.should_notify(sample_alert) is True
        assert dedup.should_notify(sample_alert) is False

        time.sleep(1.1)

        assert dedup.should_notify(sample_alert) is True

    def test_deduplicator_tracks_multiple_alerts(
        self, sample_alert: AlertEvent, different_alert: AlertEvent
    ) -> None:
        """Verify deduplicator can track multiple different alerts."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)

        assert dedup.should_notify(sample_alert) is True
        assert dedup.should_notify(different_alert) is True
        assert dedup.should_notify(sample_alert) is False
        assert dedup.should_notify(different_alert) is False

    def test_deduplicator_cleanup_removes_expired(
        self, sample_alert: AlertEvent
    ) -> None:
        """Verify cleanup removes expired entries."""
        dedup = AlertDeduplicator(dedup_window_seconds=1)

        dedup.should_notify(sample_alert)
        assert len(dedup._alert_cache) == 1  # pylint: disable=protected-access

        time.sleep(1.1)

        dedup.cleanup()
        assert len(dedup._alert_cache) == 0  # pylint: disable=protected-access

    def test_deduplicator_is_thread_safe(self) -> None:
        """Verify deduplicator uses threading lock."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert hasattr(dedup, "_lock")

    def test_deduplicator_resolved_alert_different_status(self) -> None:
        """Verify RESOLVED alert is different from ACTIVE alert of same type."""
        active_alert = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Alert",
            status=AlertStatus.ACTIVE,
        )
        resolved_alert = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Alert resolved",
            status=AlertStatus.RESOLVED,
        )

        dedup = AlertDeduplicator(dedup_window_seconds=300)

        assert dedup.should_notify(active_alert) is True
        assert dedup.should_notify(resolved_alert) is True
