"""Tests for alert deduplication logic."""

import pytest
import time
from unittest.mock import MagicMock, patch
from app.alerts.models import AlertEvent, AlertType, AlertSeverity, AlertStatus
from app.alerts.deduplicator import AlertDeduplicator


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

    def test_deduplicator_creation(self):
        """Verify AlertDeduplicator can be instantiated."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert isinstance(dedup, AlertDeduplicator)

    def test_deduplicator_stores_window_size(self):
        """Verify AlertDeduplicator stores deduplication window."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert dedup.dedup_window_seconds == 300

    def test_first_alert_should_notify(self, sample_alert):
        """Verify first alert of a type should be notified."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)

        result = dedup.should_notify(sample_alert)
        assert result is True

    def test_same_alert_twice_within_window_not_notify(self, sample_alert):
        """Verify same alert twice within window is deduped."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)

        # First alert should notify
        result1 = dedup.should_notify(sample_alert)
        assert result1 is True

        # Same alert immediately after should not notify
        result2 = dedup.should_notify(sample_alert)
        assert result2 is False

    def test_different_alert_types_notify_separately(
        self, sample_alert, different_alert
    ):
        """Verify different alert types are not deduplicated together."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)

        result1 = dedup.should_notify(sample_alert)
        assert result1 is True

        result2 = dedup.should_notify(different_alert)
        assert result2 is True

    def test_alert_notify_after_window_expires(self, sample_alert):
        """Verify alert notifies again after dedup window expires."""
        dedup = AlertDeduplicator(dedup_window_seconds=1)

        # First alert
        result1 = dedup.should_notify(sample_alert)
        assert result1 is True

        # Duplicate immediately after
        result2 = dedup.should_notify(sample_alert)
        assert result2 is False

        # Wait for window to expire
        time.sleep(1.1)

        # Same alert should notify again
        result3 = dedup.should_notify(sample_alert)
        assert result3 is True

    def test_deduplicator_tracks_multiple_alerts(
        self, sample_alert, different_alert
    ):
        """Verify deduplicator can track multiple different alerts."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)

        # Send multiple alerts
        assert dedup.should_notify(sample_alert) is True
        assert dedup.should_notify(different_alert) is True

        # Duplicates of each should be deduped
        assert dedup.should_notify(sample_alert) is False
        assert dedup.should_notify(different_alert) is False

    def test_deduplicator_cleanup_removes_expired(self, sample_alert):
        """Verify cleanup removes expired entries."""
        dedup = AlertDeduplicator(dedup_window_seconds=1)

        # Record alert
        dedup.should_notify(sample_alert)

        # Verify it's tracked
        assert len(dedup._alert_cache) == 1

        # Wait for window to expire
        time.sleep(1.1)

        # Cleanup should remove it
        dedup.cleanup()
        assert len(dedup._alert_cache) == 0

    def test_deduplicator_is_thread_safe(self, sample_alert):
        """Verify deduplicator uses threading lock."""
        dedup = AlertDeduplicator(dedup_window_seconds=300)
        assert hasattr(dedup, "_lock")

    def test_deduplicator_resolved_alert_different_status(self):
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

        # Active alert
        assert dedup.should_notify(active_alert) is True

        # Same type but resolved should notify (different status)
        # This allows resolved messages to go through even if active was just sent
        assert dedup.should_notify(resolved_alert) is True
