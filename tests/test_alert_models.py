"""Tests for alert data models and types."""

import pytest
from app.alerts.models import (
    AlertType,
    AlertStatus,
    AlertSeverity,
    AlertEvent,
    AlertConfig,
)


class TestAlertType:
    """Test AlertType enum."""

    def test_alert_type_values(self):
        """Verify AlertType has all required members."""
        assert hasattr(AlertType, "LATENCY")
        assert hasattr(AlertType, "ERROR_RATE")
        assert hasattr(AlertType, "SERVICE_DOWN")

    def test_alert_type_is_enum(self):
        """Verify AlertType is an enum."""
        from enum import Enum
        assert issubclass(AlertType, Enum)

    def test_alert_type_string_value(self):
        """Verify AlertType members have string values."""
        assert AlertType.LATENCY.value == "latency"
        assert AlertType.ERROR_RATE.value == "error_rate"
        assert AlertType.SERVICE_DOWN.value == "service_down"


class TestAlertStatus:
    """Test AlertStatus enum."""

    def test_alert_status_values(self):
        """Verify AlertStatus has all required members."""
        assert hasattr(AlertStatus, "ACTIVE")
        assert hasattr(AlertStatus, "RESOLVED")

    def test_alert_status_is_enum(self):
        """Verify AlertStatus is an enum."""
        from enum import Enum
        assert issubclass(AlertStatus, Enum)

    def test_alert_status_string_value(self):
        """Verify AlertStatus members have string values."""
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.RESOLVED.value == "resolved"


class TestAlertSeverity:
    """Test AlertSeverity enum."""

    def test_alert_severity_values(self):
        """Verify AlertSeverity has all required members."""
        assert hasattr(AlertSeverity, "LOW")
        assert hasattr(AlertSeverity, "MEDIUM")
        assert hasattr(AlertSeverity, "HIGH")
        assert hasattr(AlertSeverity, "CRITICAL")

    def test_alert_severity_is_enum(self):
        """Verify AlertSeverity is an enum."""
        from enum import Enum
        assert issubclass(AlertSeverity, Enum)

    def test_alert_severity_ordering(self):
        """Verify AlertSeverity has numeric values for ordering."""
        assert AlertSeverity.LOW.value < AlertSeverity.MEDIUM.value
        assert AlertSeverity.MEDIUM.value < AlertSeverity.HIGH.value
        assert AlertSeverity.HIGH.value < AlertSeverity.CRITICAL.value


class TestAlertEvent:
    """Test AlertEvent dataclass."""

    def test_alert_event_creation(self):
        """Verify AlertEvent can be created with required fields."""
        event = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Latency exceeded threshold",
            status=AlertStatus.ACTIVE,
        )
        assert event.alert_type == AlertType.LATENCY
        assert event.severity == AlertSeverity.HIGH
        assert event.message == "Latency exceeded threshold"
        assert event.status == AlertStatus.ACTIVE

    def test_alert_event_has_timestamp(self):
        """Verify AlertEvent has timestamp field."""
        event = AlertEvent(
            alert_type=AlertType.ERROR_RATE,
            severity=AlertSeverity.MEDIUM,
            message="Error rate high",
            status=AlertStatus.ACTIVE,
        )
        assert hasattr(event, "timestamp")
        assert event.timestamp is not None

    def test_alert_event_has_context(self):
        """Verify AlertEvent can store context metadata."""
        context = {"current_latency": 6.5, "threshold": 5.0}
        event = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Latency exceeded",
            status=AlertStatus.ACTIVE,
            context=context,
        )
        assert event.context == context

    def test_alert_event_is_frozen(self):
        """Verify AlertEvent is immutable (frozen)."""
        event = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Alert",
            status=AlertStatus.ACTIVE,
        )
        with pytest.raises((AttributeError, TypeError)):
            event.message = "Modified"

    def test_alert_event_unique_key(self):
        """Verify AlertEvent can generate a unique key for deduplication."""
        event = AlertEvent(
            alert_type=AlertType.LATENCY,
            severity=AlertSeverity.HIGH,
            message="Latency exceeded",
            status=AlertStatus.ACTIVE,
        )
        assert hasattr(event, "unique_key")
        key = event.unique_key()
        assert isinstance(key, str)
        assert len(key) > 0


class TestAlertConfig:
    """Test AlertConfig dataclass."""

    def test_alert_config_creation(self):
        """Verify AlertConfig can be created with thresholds."""
        config = AlertConfig(
            latency_threshold=5.0,
            error_rate_threshold=0.05,
            service_down_threshold=30,
        )
        assert config.latency_threshold == 5.0
        assert config.error_rate_threshold == 0.05
        assert config.service_down_threshold == 30

    def test_alert_config_default_values(self):
        """Verify AlertConfig has sensible defaults."""
        config = AlertConfig()
        assert config.latency_threshold > 0
        assert 0 <= config.error_rate_threshold <= 1
        assert config.service_down_threshold > 0

    def test_alert_config_validation_latency(self):
        """Verify latency threshold must be positive."""
        with pytest.raises(ValueError):
            AlertConfig(latency_threshold=-1.0)

        with pytest.raises(ValueError):
            AlertConfig(latency_threshold=0.0)

    def test_alert_config_validation_error_rate(self):
        """Verify error_rate must be between 0 and 1."""
        with pytest.raises(ValueError):
            AlertConfig(error_rate_threshold=-0.1)

        with pytest.raises(ValueError):
            AlertConfig(error_rate_threshold=1.5)

    def test_alert_config_validation_service_down(self):
        """Verify service_down threshold must be positive."""
        with pytest.raises(ValueError):
            AlertConfig(service_down_threshold=-10)

        with pytest.raises(ValueError):
            AlertConfig(service_down_threshold=0)

    def test_alert_config_is_frozen(self):
        """Verify AlertConfig is immutable (frozen)."""
        config = AlertConfig()
        with pytest.raises((AttributeError, TypeError)):
            config.latency_threshold = 100.0
