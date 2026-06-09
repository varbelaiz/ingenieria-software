"""Global test configuration and fixtures."""

from collections.abc import Iterator
import importlib.util
import os
from typing import Any

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


def _connect_to_test_warehouse() -> Any:
    if importlib.util.find_spec("psycopg2") is None:
        pytest.skip("psycopg2 is not installed")

    import psycopg2

    return psycopg2.connect(
        host=os.getenv("TEST_WAREHOUSE_HOST", os.getenv("WAREHOUSE_HOST", "localhost")),
        port=int(os.getenv("TEST_WAREHOUSE_PORT", os.getenv("WAREHOUSE_PORT", "5433"))),
        user=os.getenv("TEST_WAREHOUSE_USER", os.getenv("WAREHOUSE_USER", "warehouse")),
        password=os.getenv(
            "TEST_WAREHOUSE_PASSWORD", os.getenv("WAREHOUSE_PASSWORD", "warehouse")
        ),
        dbname=os.getenv("TEST_WAREHOUSE_DB", os.getenv("WAREHOUSE_DB", "warehouse")),
    )


@pytest.fixture
def warehouse_connection() -> Iterator[Any]:
    """Provide a PostgreSQL connection for bronze integration tests."""
    if importlib.util.find_spec("psycopg2") is None:
        pytest.skip("psycopg2 is not installed")

    import psycopg2

    try:
        conn = _connect_to_test_warehouse()
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL warehouse is not available: {exc}")

    try:
        yield conn
    finally:
        conn.close()
