"""Integration tests for bronze table schemas."""

from typing import Any


def test_produccion_raw_has_source_and_technical_columns(
    warehouse_connection: Any,
) -> None:
    """The production bronze table should include raw and load metadata columns."""
    from data_platform.extraction.bronze_loader import BronzeLoad, load_bronze_table

    load_bronze_table(
        warehouse_connection,
        BronzeLoad(
            table_name="produccion_raw",
            load_period="2026-07",
            source_url="https://example.test/produccion.csv",
            resource_id="resource-produccion",
            rows=[
                {
                    "idempresa": "YSUR",
                    "anio": "2016",
                    "mes": "1",
                    "idpozo": "135204",
                    "prod_pet": "0.000",
                    "prod_gas": "59.940",
                    "fecha_data": "2016-01-31",
                }
            ],
        ),
    )

    with warehouse_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'bronze'
              AND table_name = 'produccion_raw'
            """
        )
        columns = {row[0] for row in cursor.fetchall()}

    assert {
        "idempresa",
        "anio",
        "mes",
        "idpozo",
        "prod_pet",
        "prod_gas",
        "fecha_data",
        "_load_period",
        "_loaded_at",
        "_source_url",
        "_resource_id",
        "_row_hash",
    }.issubset(columns)


def test_pozos_raw_has_source_and_technical_columns(
    warehouse_connection: Any,
) -> None:
    """The wells bronze table should include raw and load metadata columns."""
    from data_platform.extraction.bronze_loader import BronzeLoad, load_bronze_table

    load_bronze_table(
        warehouse_connection,
        BronzeLoad(
            table_name="pozos_raw",
            load_period="2026-07",
            source_url="https://example.test/pozos.csv",
            resource_id="resource-pozos",
            rows=[
                {
                    "idpozo": "144081",
                    "sigla": "315",
                    "formprod": "FIMP",
                    "idempresa": "APEA",
                    "fecha_data": "",
                }
            ],
        ),
    )

    with warehouse_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'bronze'
              AND table_name = 'pozos_raw'
            """
        )
        columns = {row[0] for row in cursor.fetchall()}

    assert {
        "idpozo",
        "sigla",
        "formprod",
        "idempresa",
        "fecha_data",
        "_load_period",
        "_loaded_at",
        "_source_url",
        "_resource_id",
        "_row_hash",
    }.issubset(columns)
