"""Global test configuration and fixtures."""

import os

import pytest

from app.alerts import AlertConfig, MockNotifier

os.environ["API_KEY"] = "abcdef12345"


@pytest.fixture
def mock_alert_notifier() -> MockNotifier:
    """Provide a mock notifier for alert tests."""
    return MockNotifier()


@pytest.fixture
def alert_config() -> AlertConfig:
    """Provide default alert configuration for tests."""
    return AlertConfig(
        latency_threshold=5.0,
        error_rate_threshold=0.05,
        service_down_threshold=30,
    )
