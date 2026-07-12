"""Feature store lookup primitives for Phase 3 ML inference and training."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from typing import Any, Protocol

from ml.config import get_ml_settings


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class FeatureRow:  # pylint: disable=too-many-instance-attributes
    """Point-in-time well features materialized in the feature store."""

    well_id: str
    as_of_date: date
    gas_production_current: Decimal
    gas_production_avg_3m: Decimal
    gas_production_avg_6m: Decimal
    gas_production_trend_3m: Decimal
    oil_production_current: Decimal
    water_production_current: Decimal
    producing_days_available: int
    production_months_available: int
    formation: str
    basin: str
    resource_type: str


class FeatureNotFoundError(LookupError):
    """Raised when no point-in-time feature row exists for a well/date."""

    def __init__(self, *, well_id: str, as_of_date: date, schema: str) -> None:
        super().__init__(
            "No feature row found for "
            f"well_id={well_id!r} as_of_date={as_of_date.isoformat()} "
            f"in schema {schema!r}"
        )


class FeatureRepository(Protocol):
    """Repository contract implemented by local fakes and Postgres storage."""

    def lookup_features(self, well_id: str, as_of_date: date) -> FeatureRow | None:
        """Return the latest feature row available at or before ``as_of_date``."""

    def list_features(self, as_of_date: date) -> list[FeatureRow]:
        """Return all feature rows whose event time is within the cutoff."""


class FeatureStore:
    """High-level feature lookup API with controlled domain errors."""

    def __init__(
        self, repository: FeatureRepository, *, schema: str | None = None
    ) -> None:
        self._repository = repository
        self._schema = schema or get_ml_settings().feature_store_schema

    def get_features(self, well_id: str, as_of_date: date) -> FeatureRow:
        """Return point-in-time features for a well and cutoff date."""

        row = self._repository.lookup_features(well_id, as_of_date)
        if row is None:
            raise FeatureNotFoundError(
                well_id=well_id, as_of_date=as_of_date, schema=self._schema
            )
        return row


class InMemoryFeatureRepository:
    """Deterministic repository useful for unit tests and local prototyping."""

    def __init__(self, rows: Iterable[FeatureRow]) -> None:
        self._rows_by_grain: dict[tuple[str, date], FeatureRow] = {}
        for row in rows:
            self._rows_by_grain[(row.well_id, row.as_of_date)] = row

    def lookup_features(self, well_id: str, as_of_date: date) -> FeatureRow | None:
        """Return the latest row for ``well_id`` without crossing the cutoff."""

        candidates = [
            row
            for (candidate_well_id, candidate_date), row in self._rows_by_grain.items()
            if candidate_well_id == well_id and candidate_date <= as_of_date
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: row.as_of_date)

    def list_features(self, as_of_date: date) -> list[FeatureRow]:
        """Return deterministic point-in-time history for training."""

        return sorted(
            (
                row
                for row in self._rows_by_grain.values()
                if row.as_of_date <= as_of_date
            ),
            key=lambda row: (row.well_id, row.as_of_date),
        )


class PostgresFeatureRepository:
    """Postgres-backed feature repository over ``ml_features`` dbt models."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        schema: str | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._schema = schema or get_ml_settings().feature_store_schema
        self._qualified_table = (
            f"{_validate_identifier(self._schema)}.well_monthly_features"
        )

    def lookup_features(self, well_id: str, as_of_date: date) -> FeatureRow | None:
        """Read the latest persisted feature row for the requested cutoff."""

        connection = self._connection_factory()
        with _open_cursor(connection) as cursor:
            cursor.execute(
                f"""
                select
                    well_id,
                    as_of_date,
                    gas_production_current,
                    gas_production_avg_3m,
                    gas_production_avg_6m,
                    gas_production_trend_3m,
                    oil_production_current,
                    water_production_current,
                    producing_days_available,
                    production_months_available,
                    formation,
                    basin,
                    resource_type
                from {self._qualified_table}
                where well_id = %s
                  and as_of_date <= %s
                order by as_of_date desc
                limit 1
                """,
                (well_id, as_of_date),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return _row_from_mapping(row)

    def list_features(self, as_of_date: date) -> list[FeatureRow]:
        """Read complete feature history without crossing the training cutoff."""

        connection = self._connection_factory()
        with _open_cursor(connection) as cursor:
            cursor.execute(
                f"""
                select
                    well_id,
                    as_of_date,
                    gas_production_current,
                    gas_production_avg_3m,
                    gas_production_avg_6m,
                    gas_production_trend_3m,
                    oil_production_current,
                    water_production_current,
                    producing_days_available,
                    production_months_available,
                    formation,
                    basin,
                    resource_type
                from {self._qualified_table}
                where as_of_date <= %s
                order by well_id, as_of_date
                """,
                (as_of_date,),
            )
            rows = cursor.fetchall()
        return [_row_from_mapping(row) for row in rows]


def _validate_identifier(identifier: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Invalid PostgreSQL identifier: {identifier!r}")
    return identifier


def _open_cursor(connection: Any) -> Any:
    # Import lazily so default app/test installs do not require the data group.
    # pylint: disable=import-outside-toplevel
    try:
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return connection.cursor()

    try:
        return connection.cursor(cursor_factory=RealDictCursor)
    except TypeError:
        return connection.cursor()


def _row_from_mapping(row: Mapping[str, object]) -> FeatureRow:
    return FeatureRow(
        well_id=str(row["well_id"]),
        as_of_date=_as_date(row["as_of_date"]),
        gas_production_current=_as_decimal(row["gas_production_current"]),
        gas_production_avg_3m=_as_decimal(row["gas_production_avg_3m"]),
        gas_production_avg_6m=_as_decimal(row["gas_production_avg_6m"]),
        gas_production_trend_3m=_as_decimal(row["gas_production_trend_3m"]),
        oil_production_current=_as_decimal(row["oil_production_current"]),
        water_production_current=_as_decimal(row["water_production_current"]),
        producing_days_available=_as_int(row["producing_days_available"]),
        production_months_available=_as_int(row["production_months_available"]),
        formation=str(row["formation"]),
        basin=str(row["basin"]),
        resource_type=str(row["resource_type"]),
    )


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Expected date-compatible value, got {type(value).__name__}")


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, (str, Decimal)):
        return int(value)
    raise TypeError(f"Expected int-compatible value, got {type(value).__name__}")
