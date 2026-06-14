"""Transactional PostgreSQL loader for bronze raw tables."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_values

from data_platform.extraction.client import ExtractionError


BRONZE_SCHEMA = "bronze"
TECHNICAL_COLUMNS = (
    "_load_period",
    "_loaded_at",
    "_source_url",
    "_resource_id",
    "_row_hash",
)
_IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True)
class BronzeLoad:
    """Payload for loading one raw CSV resource into bronze."""

    table_name: str
    load_period: str
    source_url: str
    resource_id: str
    rows: Sequence[Mapping[str, str]]


def load_bronze_table(conn: PgConnection, bronze_load: BronzeLoad) -> int:
    """Replace one load-period partition in a bronze table."""
    _validate_identifier(bronze_load.table_name)
    source_columns = _source_columns(bronze_load.rows)
    loaded_at = datetime.now(timezone.utc)

    with conn:
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier(BRONZE_SCHEMA)
                )
            )
            _ensure_table(cursor, bronze_load.table_name, source_columns)
            cursor.execute(
                sql.SQL("DELETE FROM {}.{} WHERE _load_period = %s").format(
                    sql.Identifier(BRONZE_SCHEMA),
                    sql.Identifier(bronze_load.table_name),
                ),
                (bronze_load.load_period,),
            )
            if not bronze_load.rows:
                return 0

            all_columns = [*source_columns, *TECHNICAL_COLUMNS]
            values = [
                _row_values(row, source_columns, bronze_load, loaded_at)
                for row in bronze_load.rows
            ]
            insert_query = sql.SQL("INSERT INTO {}.{} ({}) VALUES %s").format(
                sql.Identifier(BRONZE_SCHEMA),
                sql.Identifier(bronze_load.table_name),
                sql.SQL(", ").join(sql.Identifier(column) for column in all_columns),
            )
            execute_values(cursor, insert_query, values)

    return len(bronze_load.rows)


def _ensure_table(
    cursor: Any,
    table_name: str,
    source_columns: Sequence[str],
) -> None:
    column_defs = [
        *[
            sql.SQL("{} TEXT").format(sql.Identifier(column))
            for column in source_columns
        ],
        sql.SQL("_load_period TEXT NOT NULL"),
        sql.SQL("_loaded_at TIMESTAMPTZ NOT NULL"),
        sql.SQL("_source_url TEXT NOT NULL"),
        sql.SQL("_resource_id TEXT NOT NULL"),
        sql.SQL("_row_hash TEXT NOT NULL"),
    ]
    cursor.execute(
        sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
            sql.Identifier(BRONZE_SCHEMA),
            sql.Identifier(table_name),
            sql.SQL(", ").join(column_defs),
        )
    )
    for column in source_columns:
        cursor.execute(
            sql.SQL("ALTER TABLE {}.{} ADD COLUMN IF NOT EXISTS {} TEXT").format(
                sql.Identifier(BRONZE_SCHEMA),
                sql.Identifier(table_name),
                sql.Identifier(column),
            )
        )


def _source_columns(rows: Sequence[Mapping[str, str]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            _validate_identifier(column)
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return columns


def _row_values(
    row: Mapping[str, str],
    source_columns: Sequence[str],
    bronze_load: BronzeLoad,
    loaded_at: datetime,
) -> tuple[object, ...]:
    source_values = [row.get(column, "") for column in source_columns]
    return (
        *source_values,
        bronze_load.load_period,
        loaded_at,
        bronze_load.source_url,
        bronze_load.resource_id,
        _row_hash(row),
    )


def _row_hash(row: Mapping[str, str]) -> str:
    encoded = json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_identifier(identifier: str) -> None:
    if not _IDENTIFIER_PATTERN.match(identifier):
        raise ExtractionError(f"Invalid PostgreSQL identifier: {identifier!r}")
