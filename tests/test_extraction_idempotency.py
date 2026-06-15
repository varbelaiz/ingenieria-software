"""Integration tests for idempotent bronze loading."""

# pylint: disable=wrong-import-position

from typing import Any

import pytest

pytest.importorskip("psycopg2")

from data_platform.extraction.bronze_loader import (  # noqa: E402
    BronzeLoad,
    load_bronze_table,
)

# Every test here writes to the real bronze tables; gate behind the opt-in marker.
pytestmark = pytest.mark.warehouse_mutating


def test_load_bronze_table_replaces_existing_partition(
    warehouse_connection: Any,
) -> None:
    """Running the same partition twice should not duplicate rows."""
    first_load = BronzeLoad(
        table_name="produccion_raw",
        load_period="2026-06",
        source_url="https://example.test/produccion.csv",
        resource_id="resource-produccion",
        rows=[
            {"idempresa": "YSUR", "anio": "2016", "mes": "1", "idpozo": "135204"},
            {"idempresa": "YPF", "anio": "2016", "mes": "1", "idpozo": "155584"},
        ],
    )
    second_load = BronzeLoad(
        table_name="produccion_raw",
        load_period="2026-06",
        source_url="https://example.test/produccion.csv",
        resource_id="resource-produccion",
        rows=[
            {"idempresa": "PAMPA", "anio": "2016", "mes": "1", "idpozo": "200001"},
        ],
    )

    load_bronze_table(warehouse_connection, first_load)
    load_bronze_table(warehouse_connection, second_load)

    with warehouse_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*), MIN(idempresa)
            FROM bronze.produccion_raw
            WHERE _load_period = %s
            """,
            ("2026-06",),
        )
        row_count, only_company = cursor.fetchone()

    assert row_count == 1
    assert only_company == "PAMPA"


def test_load_bronze_table_same_rows_twice_is_idempotent(
    warehouse_connection: Any,
) -> None:
    """Loading the exact same rows a second time keeps the row count unchanged."""
    bronze_load = BronzeLoad(
        table_name="produccion_raw",
        load_period="2026-05",
        source_url="https://example.test/produccion.csv",
        resource_id="resource-produccion",
        rows=[
            {"idempresa": "YSUR", "anio": "2016", "mes": "1", "idpozo": "135204"},
            {"idempresa": "YPF", "anio": "2016", "mes": "1", "idpozo": "155584"},
        ],
    )

    load_bronze_table(warehouse_connection, bronze_load)
    load_bronze_table(warehouse_connection, bronze_load)

    with warehouse_connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM bronze.produccion_raw WHERE _load_period = %s",
            ("2026-05",),
        )
        (row_count,) = cursor.fetchone()

    assert row_count == 2
