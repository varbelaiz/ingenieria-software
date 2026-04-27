"""Alert data models and types for monitoring service health."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AlertType(Enum):
    """Types of alerts that can be triggered."""

    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    SERVICE_DOWN = "service_down"


class AlertStatus(Enum):
    """Status of an alert."""

    ACTIVE = "active"
    RESOLVED = "resolved"


class AlertSeverity(Enum):
    """Severity levels for alerts."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class AlertEvent:
    """Represents a single alert event."""

    alert_type: AlertType
    severity: AlertSeverity
    message: str
    status: AlertStatus
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    context: Optional[dict[str, Any]] = None

    def unique_key(self) -> str:
        """Generate a unique key for deduplication based on alert type and status."""
        return f"{self.alert_type.value}:{self.status.value}"


@dataclass(frozen=True)
class AlertConfig:
    """Configuration for alert thresholds."""

    latency_threshold: float = 5.0
    error_rate_threshold: float = 0.05
    service_down_threshold: int = 30

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.latency_threshold <= 0:
            raise ValueError("latency_threshold must be positive")
        if not (0 <= self.error_rate_threshold <= 1):
            raise ValueError("error_rate_threshold must be between 0 and 1")
        if self.service_down_threshold <= 0:
            raise ValueError("service_down_threshold must be positive")
