"""Integration tests for idempotent bronze loading."""

from typing import Any


def test_load_bronze_table_replaces_existing_partition(
    warehouse_connection: Any,
) -> None:
    """Running the same partition twice should not duplicate rows."""
    from data_platform.extraction.bronze_loader import BronzeLoad, load_bronze_table

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
