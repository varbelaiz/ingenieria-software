"""End-to-end checks against a live, provisioned Metabase instance.

Unlike :mod:`tests.test_metabase_config` (pure structure) and
:mod:`tests.test_metabase_cards_sql` (SQL vs. gold), these tests assert the *result*
of provisioning by talking to the running Metabase REST API: the dashboard and cards
exist, the petróleo card is no longer truncated, the secondary axis and conditional
formatting are applied, the quality table spans the full width, and the bundled sample
content has been removed.

They assume the data stack is up and ``python -m data_platform.bi.provision`` has been
run. The whole module is skipped when Metabase is not reachable, mirroring the
``warehouse_connection`` skip pattern in :mod:`tests.conftest`.

Run after provisioning:
    uv run --group data pytest tests/test_metabase_e2e.py
"""

# pylint: disable=wrong-import-position

from __future__ import annotations

from typing import Any

import pytest

requests = pytest.importorskip("requests")

from data_platform.bi import metabase_config  # noqa: E402
from data_platform.bi.provision import (  # noqa: E402
    MetabaseClient,
    settings_from_env,
)

HEALTH_TIMEOUT_SECONDS = 5
PETROLEO_CARD = "Producción de petróleo por operadora"
EVOLUCION_CARD = "Evolución mensual de producción total"
QUALITY_CARD = "Marca de calidad de los datos"
GRID_WIDTH = 24


@pytest.fixture
def metabase_client() -> MetabaseClient:
    """Authenticated Metabase client, skipping when the instance is unreachable."""
    settings = settings_from_env()
    health_url = f"{settings.base_url}/api/health"
    try:
        response = requests.get(health_url, timeout=HEALTH_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        pytest.skip(f"Metabase is not reachable at {settings.base_url}: {exc}")
    if not response.ok:
        pytest.skip(f"Metabase health check failed at {settings.base_url}")

    client = MetabaseClient(settings)
    client.authenticate()
    return client


def _as_list(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        return list(response.get("data", []))
    return list(response)


def _card_by_name(client: MetabaseClient, name: str) -> dict[str, Any]:
    for card in _as_list(client.request("GET", "/card")):
        if card.get("name") == name:
            return card
    raise AssertionError(f"card not found in Metabase: {name}")


def _run_card(
    client: MetabaseClient, card_id: int
) -> tuple[list[str], list[list[Any]]]:
    result = client.request_dict("POST", f"/card/{card_id}/query", json={})
    data = result["data"]
    cols = [col["name"] for col in data["cols"]]
    return cols, list(data["rows"])


def test_petroleo_card_is_not_truncated(
    metabase_client: MetabaseClient, warehouse_connection: Any
) -> None:
    """The petróleo card spans the full warehouse history and buckets into 'Otras'."""
    with warehouse_connection.cursor() as cursor:
        cursor.execute("select max(periodo) from gold.fct_produccion")
        (warehouse_max,) = cursor.fetchone()

    card = _card_by_name(metabase_client, PETROLEO_CARD)
    cols, rows = _run_card(metabase_client, int(card["id"]))
    periodo_idx = cols.index("periodo")
    operadora_idx = cols.index("operadora")

    # The most recent period reaching the card must match the warehouse, i.e. the
    # default 2000-row cap is no longer chopping off recent data.
    card_max_periodo = max(str(row[periodo_idx])[:7] for row in rows)
    assert card_max_periodo == warehouse_max.strftime("%Y-%m")

    operadoras = {row[operadora_idx] for row in rows}
    assert "Otras" in operadoras
    # Top 8 operadoras plus the 'Otras' bucket.
    assert len(operadoras) == 9
    assert len(rows) < 100_000


def test_evolucion_card_uses_secondary_axis(metabase_client: MetabaseClient) -> None:
    """Petróleo and agua are pinned to the right axis on the evolución card."""
    card = _card_by_name(metabase_client, EVOLUCION_CARD)
    series_settings = card["visualization_settings"]["series_settings"]
    assert series_settings["prod_petroleo"]["axis"] == "right"
    assert series_settings["prod_agua"]["axis"] == "right"


def test_quality_card_has_conditional_formatting(
    metabase_client: MetabaseClient,
) -> None:
    """The quality table colours its status column by PASS/ERROR."""
    card = _card_by_name(metabase_client, QUALITY_CARD)
    rules = card["visualization_settings"]["table.column_formatting"]
    statuses = {rule["value"] for rule in rules}
    assert statuses == {"PASS", "ERROR"}


def test_quality_card_is_full_width(metabase_client: MetabaseClient) -> None:
    """The quality table dashcard spans the full dashboard grid width."""
    dashboard = metabase_config.DASHBOARD
    quality_id = int(_card_by_name(metabase_client, QUALITY_CARD)["id"])

    dashboard_id: int | None = None
    for existing in _as_list(metabase_client.request("GET", "/dashboard")):
        if existing.get("name") == dashboard.name:
            dashboard_id = int(existing["id"])
            break
    assert dashboard_id is not None, "provisioned dashboard not found"

    detail = metabase_client.request_dict("GET", f"/dashboard/{dashboard_id}")
    widths = [
        dashcard["size_x"]
        for dashcard in detail.get("dashcards", [])
        if dashcard.get("card_id") == quality_id
    ]
    assert widths == [GRID_WIDTH]


def test_sample_content_is_removed(metabase_client: MetabaseClient) -> None:
    """Metabase's bundled sample database and demo dashboard are gone."""
    databases = _as_list(metabase_client.request("GET", "/database"))
    assert not any(db.get("is_sample") for db in databases)

    dashboards = _as_list(metabase_client.request("GET", "/dashboard"))
    names = {dashboard.get("name") for dashboard in dashboards}
    assert "E-commerce Insights" not in names
