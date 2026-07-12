"""Tests for the Phase 3 feature store foundation."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ml.features.store import (
    FeatureNotFoundError,
    FeatureRow,
    FeatureStore,
    InMemoryFeatureRepository,
    PostgresFeatureRepository,
)


def _feature_row(
    well_id: str,
    as_of_date: date,
    production_current: Decimal,
) -> FeatureRow:
    return FeatureRow(
        well_id=well_id,
        as_of_date=as_of_date,
        gas_production_current=production_current,
        gas_production_avg_3m=Decimal("90.0"),
        gas_production_avg_6m=Decimal("85.0"),
        gas_production_trend_3m=Decimal("-2.5"),
        oil_production_current=Decimal("12.0"),
        water_production_current=Decimal("4.0"),
        producing_days_available=28,
        production_months_available=6,
        formation="Vaca Muerta",
        basin="Neuquina",
        resource_type="Shale",
    )


def test_get_features_returns_latest_row_at_or_before_as_of_date() -> None:
    """Return the point-in-time features available at the requested cutoff."""

    repository = InMemoryFeatureRepository(
        [
            _feature_row("POZO-001", date(2024, 1, 1), Decimal("100.0")),
            _feature_row("POZO-001", date(2024, 3, 1), Decimal("75.0")),
            _feature_row("POZO-001", date(2024, 5, 1), Decimal("50.0")),
        ]
    )
    store = FeatureStore(repository)

    row = store.get_features("POZO-001", date(2024, 4, 15))

    assert row.well_id == "POZO-001"
    assert row.as_of_date == date(2024, 3, 1)
    assert row.gas_production_current == Decimal("75.0")


def test_get_features_does_not_use_future_rows() -> None:
    """Do not leak features materialized after the requested cutoff."""

    repository = InMemoryFeatureRepository(
        [_feature_row("POZO-001", date(2024, 5, 1), Decimal("50.0"))]
    )
    store = FeatureStore(repository)

    with pytest.raises(FeatureNotFoundError, match="POZO-001.*2024-04-01"):
        store.get_features("POZO-001", date(2024, 4, 1))


def test_get_features_raises_clear_error_when_missing() -> None:
    """Expose a controlled domain error when features are absent."""

    store = FeatureStore(InMemoryFeatureRepository([]))

    with pytest.raises(FeatureNotFoundError) as exc_info:
        store.get_features("POZO-404", date(2024, 4, 1))

    assert "POZO-404" in str(exc_info.value)
    assert "2024-04-01" in str(exc_info.value)
    assert "ml_features" in str(exc_info.value)


def test_in_memory_repository_replaces_duplicate_well_date_rows() -> None:
    """Keep rematerialization idempotent for the same well/date grain."""

    repository = InMemoryFeatureRepository(
        [
            _feature_row("POZO-001", date(2024, 3, 1), Decimal("75.0")),
            _feature_row("POZO-001", date(2024, 3, 1), Decimal("80.0")),
        ]
    )

    row = repository.lookup_features("POZO-001", date(2024, 3, 1))

    assert row is not None
    assert row.gas_production_current == Decimal("80.0")


def test_postgres_repository_uses_configured_schema_and_cutoff_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the Postgres lookup against the configured feature schema."""

    captured: dict[str, Any] = {}

    class Cursor:
        """Minimal DB-API cursor fake for query inspection."""

        def __enter__(self) -> "Cursor":
            """Return the cursor context manager value."""
            return self

        def __exit__(self, *args: object) -> None:
            """Close the cursor context manager."""
            return None

        def execute(self, query: str, params: tuple[str, date]) -> None:
            """Capture the SQL query and params sent by the repository."""
            captured["query"] = query
            captured["params"] = params

        def fetchone(self) -> dict[str, object]:
            """Return one dict row shaped like psycopg2 RealDictCursor output."""
            return {
                "well_id": "POZO-001",
                "as_of_date": date(2024, 3, 1),
                "gas_production_current": Decimal("75.0"),
                "gas_production_avg_3m": Decimal("90.0"),
                "gas_production_avg_6m": Decimal("85.0"),
                "gas_production_trend_3m": Decimal("-2.5"),
                "oil_production_current": Decimal("12.0"),
                "water_production_current": Decimal("4.0"),
                "producing_days_available": 28,
                "production_months_available": 6,
                "formation": "Vaca Muerta",
                "basin": "Neuquina",
                "resource_type": "Shale",
            }

    class Connection:
        """Minimal connection fake returning the cursor above."""

        def cursor(self) -> Cursor:
            """Return a DB-API cursor fake."""
            return Cursor()

    monkeypatch.setenv("ML_FEATURE_STORE_SCHEMA", "custom_features")
    repository = PostgresFeatureRepository(Connection)

    row = repository.lookup_features("POZO-001", date(2024, 4, 1))

    assert row is not None
    assert row.as_of_date == date(2024, 3, 1)
    assert "custom_features.well_monthly_features" in captured["query"]
    assert "as_of_date <= %s" in captured["query"]
    assert "order by as_of_date desc" in captured["query"].lower()
    assert captured["params"] == ("POZO-001", date(2024, 4, 1))


def test_dbt_feature_model_is_incremental_and_idempotent() -> None:
    """Persist feature rows at the expected well/date grain."""

    model_path = Path(
        "data_platform/transform/models/ml_features/well_monthly_features.sql"
    )

    model_sql = model_path.read_text(encoding="utf-8")

    assert "schema='ml_features'" in model_sql
    assert "materialized='incremental'" in model_sql
    assert "incremental_strategy='merge'" in model_sql
    assert "unique_key=['well_id', 'as_of_date']" in model_sql


def test_dbt_feature_model_prevents_temporal_leakage() -> None:
    """Only use production records available at or before each feature date."""

    model_path = Path(
        "data_platform/transform/models/ml_features/well_monthly_features.sql"
    )

    model_sql = model_path.read_text(encoding="utf-8").lower()

    assert "history.periodo <= feature_dates.as_of_date" in model_sql
    assert "future" not in model_sql
