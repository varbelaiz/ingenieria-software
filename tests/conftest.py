"""Global test configuration and fixtures."""

from collections.abc import Iterator
import os
from typing import Any

import pytest

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from app.alerts import AlertConfig, MockNotifier

os.environ["API_KEY"] = "abcdef12345"

# Tests marked ``warehouse_mutating`` DROP/seed the real warehouse (bronze/silver/gold)
# and do not restore it. They are meant for an ephemeral CI warehouse, so they are
# skipped unless this env var is set, to stop a stray local ``pytest`` from wiping a
# warehouse that holds real data.
RUN_WAREHOUSE_MUTATING_TESTS_ENV = "RUN_WAREHOUSE_MUTATING_TESTS"


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker for warehouse-mutating integration tests."""
    config.addinivalue_line(
        "markers",
        "warehouse_mutating: drops/seeds the real warehouse; skipped unless "
        f"{RUN_WAREHOUSE_MUTATING_TESTS_ENV}=1",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip warehouse-mutating tests unless explicitly opted in via env var."""
    del config
    if os.getenv(RUN_WAREHOUSE_MUTATING_TESTS_ENV):
        return
    skip_marker = pytest.mark.skip(
        reason=(
            "warehouse-mutating test; set "
            f"{RUN_WAREHOUSE_MUTATING_TESTS_ENV}=1 to run "
            "(do not run against a warehouse with real data)"
        )
    )
    for item in items:
        if "warehouse_mutating" in item.keywords:
            item.add_marker(skip_marker)


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
    if psycopg2 is None:
        pytest.skip("psycopg2 is not installed")

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
    if psycopg2 is None:
        pytest.skip("psycopg2 is not installed")

    try:
        conn = _connect_to_test_warehouse()
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL warehouse is not available: {exc}")

    try:
        yield conn
    finally:
        conn.close()
