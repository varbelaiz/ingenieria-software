"""Smoke test that every Metabase card SQL is valid against the gold warehouse.

This is the BI equivalent of a connection check: each card is the exact native query
Metabase will issue, so running ``EXPLAIN`` against the live gold schema proves the
queries reference real tables and columns. It uses the shared ``warehouse_connection``
fixture and is skipped when no warehouse (or no built gold layer) is available.
"""

# pylint: disable=wrong-import-position

from __future__ import annotations

from typing import Any

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data_platform.bi import metabase_config  # noqa: E402

REQUIRED_GOLD_TABLES = ("fct_produccion", "quality_marks")


def _gold_is_built(connection: Any) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select count(*)
            from information_schema.tables
            where table_schema = 'gold'
              and table_name = any(%s)
            """,
            (list(REQUIRED_GOLD_TABLES),),
        )
        (count,) = cursor.fetchone()
    return bool(count == len(REQUIRED_GOLD_TABLES))


@pytest.fixture
def gold_connection(warehouse_connection: Any) -> Any:
    """Yield a warehouse connection, skipping if the gold layer is not built."""
    if not _gold_is_built(warehouse_connection):
        pytest.skip("gold layer is not built in the warehouse")
    return warehouse_connection


@pytest.mark.parametrize(
    "card", metabase_config.CARDS, ids=[card.name for card in metabase_config.CARDS]
)
def test_card_sql_explains_against_gold(card: Any, gold_connection: Any) -> None:
    """Each card's native SQL must EXPLAIN cleanly against the real gold schema."""
    with gold_connection.cursor() as cursor:
        try:
            cursor.execute(f"EXPLAIN {card.sql}")
        finally:
            gold_connection.rollback()
