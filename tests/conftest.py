"""Global test configuration and fixtures."""

import os

import pytest

os.environ["API_KEY"] = "abcdef12345"


@pytest.fixture
def mock_alert_notifier():
    """Provide a mock notifier for alert tests."""
    from app.alerts import MockNotifier

    return MockNotifier()


@pytest.fixture
def alert_config():
    """Provide default alert configuration for tests."""
    from app.alerts import AlertConfig

    return AlertConfig(
        latency_threshold=5.0,
        error_rate_threshold=0.05,
        service_down_threshold=30,
    )
