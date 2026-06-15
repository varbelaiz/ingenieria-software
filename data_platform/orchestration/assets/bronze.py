"""Dagster assets that land datos.gob.ar resources into bronze."""

from collections.abc import Iterator
from contextlib import contextmanager
import os

from dagster import AssetExecutionContext, MonthlyPartitionsDefinition, asset
import psycopg2
from psycopg2.extensions import connection as PgConnection

from data_platform.extraction.bronze_loader import BronzeLoad, load_bronze_table
from data_platform.extraction.pozos import (
    POZOS_DEFAULT_URL,
    POZOS_RESOURCE_ID,
    POZOS_URL_ENV,
    fetch_pozos_rows,
)
from data_platform.extraction.produccion import (
    PRODUCCION_DEFAULT_URL,
    PRODUCCION_RESOURCE_ID,
    PRODUCCION_URL_ENV,
    fetch_produccion_rows,
)


bronze_monthly_partitions = MonthlyPartitionsDefinition(start_date="2026-01-01")


@asset(partitions_def=bronze_monthly_partitions, group_name="bronze")
def bronze_produccion_raw(context: AssetExecutionContext) -> int:
    """Load raw non-conventional production rows into bronze.produccion_raw."""
    rows = fetch_produccion_rows()
    with warehouse_connection() as conn:
        row_count = load_bronze_table(
            conn,
            BronzeLoad(
                table_name="produccion_raw",
                load_period=context.partition_key,
                source_url=os.getenv(PRODUCCION_URL_ENV, PRODUCCION_DEFAULT_URL),
                resource_id=PRODUCCION_RESOURCE_ID,
                rows=rows,
            ),
        )
    context.log.info("Loaded %s rows into bronze.produccion_raw", row_count)
    return row_count


@asset(partitions_def=bronze_monthly_partitions, group_name="bronze")
def bronze_pozos_raw(context: AssetExecutionContext) -> int:
    """Load raw operator-submitted well rows into bronze.pozos_raw."""
    rows = fetch_pozos_rows()
    with warehouse_connection() as conn:
        row_count = load_bronze_table(
            conn,
            BronzeLoad(
                table_name="pozos_raw",
                load_period=context.partition_key,
                source_url=os.getenv(POZOS_URL_ENV, POZOS_DEFAULT_URL),
                resource_id=POZOS_RESOURCE_ID,
                rows=rows,
            ),
        )
    context.log.info("Loaded %s rows into bronze.pozos_raw", row_count)
    return row_count


@contextmanager
def warehouse_connection() -> Iterator[PgConnection]:
    """Open a PostgreSQL warehouse connection from environment variables."""
    conn = psycopg2.connect(
        host=os.getenv("WAREHOUSE_HOST", "localhost"),
        port=int(os.getenv("WAREHOUSE_PORT", "5433")),
        user=os.getenv("WAREHOUSE_USER", "warehouse"),
        password=os.getenv("WAREHOUSE_PASSWORD", "warehouse"),
        dbname=os.getenv("WAREHOUSE_DB", "warehouse"),
    )
    try:
        yield conn
    finally:
        conn.close()


bronze_assets = [bronze_produccion_raw, bronze_pozos_raw]
