"""Idempotent provisioning of Metabase BI assets via its REST API.

Reads the declarative definitions in :mod:`data_platform.bi.metabase_config` and
applies them against a running Metabase instance: bootstraps the admin user (first
run), registers the warehouse as a data source, and upserts the collection, cards and
dashboard. Re-running the script converges to the same state without creating
duplicates.

Usage:
    python -m data_platform.bi.provision

Configuration is taken from environment variables (see ``.env.data.example``):
    METABASE_URL, METABASE_ADMIN_EMAIL, METABASE_ADMIN_PASSWORD,
    METABASE_ADMIN_FIRST_NAME, METABASE_ADMIN_LAST_NAME,
    METABASE_WAREHOUSE_HOST, METABASE_WAREHOUSE_PORT,
    WAREHOUSE_DB, METABASE_WAREHOUSE_USER, METABASE_WAREHOUSE_PASSWORD.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import sys
import time
from typing import Any, cast

import requests

from data_platform.bi import metabase_config
from data_platform.bi.metabase_config import Card

REQUEST_TIMEOUT = 30
HEALTH_RETRIES = 40
HEALTH_DELAY_SECONDS = 3

# Metabase dashboard grid is 24 columns wide; lay cards out two per row.
GRID_WIDTH = 24
CARD_WIDTH = 12
CARD_HEIGHT = 8


@dataclass(frozen=True)
class MetabaseSettings:  # pylint: disable=too-many-instance-attributes
    """Connection and bootstrap settings resolved from the environment."""

    base_url: str
    admin_email: str
    admin_password: str
    admin_first_name: str
    admin_last_name: str
    warehouse_host: str
    warehouse_port: int
    warehouse_db: str
    metabase_warehouse_user: str
    metabase_warehouse_password: str


def settings_from_env() -> MetabaseSettings:
    """Build :class:`MetabaseSettings` from environment variables with sane defaults."""
    return MetabaseSettings(
        base_url=os.getenv("METABASE_URL", "http://localhost:3002").rstrip("/"),
        admin_email=os.getenv("METABASE_ADMIN_EMAIL", "admin@example.com"),
        admin_password=os.getenv("METABASE_ADMIN_PASSWORD", "metabase123"),
        admin_first_name=os.getenv("METABASE_ADMIN_FIRST_NAME", "Data"),
        admin_last_name=os.getenv("METABASE_ADMIN_LAST_NAME", "Admin"),
        warehouse_host=os.getenv("METABASE_WAREHOUSE_HOST", "warehouse"),
        warehouse_port=int(os.getenv("METABASE_WAREHOUSE_PORT", "5432")),
        warehouse_db=os.getenv("WAREHOUSE_DB", "warehouse"),
        metabase_warehouse_user=os.getenv("METABASE_WAREHOUSE_USER", "metabase_ro"),
        metabase_warehouse_password=os.getenv("METABASE_WAREHOUSE_PASSWORD", ""),
    )


class MetabaseClient:
    """Thin authenticated wrapper around the Metabase REST API."""

    def __init__(self, settings: MetabaseSettings) -> None:
        self._settings = settings
        self._session = requests.Session()
        self._token: str | None = None

    def _url(self, path: str) -> str:
        return f"{self._settings.base_url}/api{path}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token is not None:
            headers["X-Metabase-Session"] = self._token
        return headers

    def request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any] | list[Any] | None:
        """Issue an API request and return the parsed JSON body (or ``None``)."""
        response = self._session.request(
            method,
            self._url(path),
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
        if not response.content:
            return None
        return cast(dict[str, Any] | list[Any] | None, response.json())

    def request_dict(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Like :meth:`request` but asserts the response is a JSON object."""
        result = self.request(method, path, **kwargs)
        return cast(dict[str, Any], result)

    def wait_until_healthy(self) -> None:
        """Block until the Metabase health endpoint reports ready."""
        for attempt in range(1, HEALTH_RETRIES + 1):
            try:
                response = self._session.get(
                    self._url("/health"), timeout=REQUEST_TIMEOUT
                )
                if response.ok:
                    return
            except requests.RequestException:
                pass
            print(f"Waiting for Metabase to be healthy ({attempt}/{HEALTH_RETRIES})...")
            time.sleep(HEALTH_DELAY_SECONDS)
        raise RuntimeError("Metabase did not become healthy in time")

    def authenticate(self) -> None:
        """Bootstrap the admin user on first run, otherwise log in.

        Metabase keeps a non-null ``setup-token`` in the properties even after the
        instance is set up, so the decision is gated on ``has-user-setup`` to stay
        idempotent across runs.
        """
        properties = self.request_dict("GET", "/session/properties")
        setup_token = properties.get("setup-token")
        has_user_setup = bool(properties.get("has-user-setup"))
        if setup_token and not has_user_setup:
            self._token = self._run_setup(setup_token)
        else:
            self._token = self._login()

    def _run_setup(self, setup_token: str) -> str:
        payload = {
            "token": setup_token,
            "user": {
                "first_name": self._settings.admin_first_name,
                "last_name": self._settings.admin_last_name,
                "email": self._settings.admin_email,
                "password": self._settings.admin_password,
                "site_name": "Plataforma de Datos",
            },
            "prefs": {
                "site_name": "Plataforma de Datos",
                "allow_tracking": False,
            },
        }
        result = self.request_dict("POST", "/setup", json=payload)
        return str(result["id"])

    def _login(self) -> str:
        payload = {
            "username": self._settings.admin_email,
            "password": self._settings.admin_password,
        }
        result = self.request_dict("POST", "/session", json=payload)
        return str(result["id"])


def _as_list(response: Any) -> list[dict[str, Any]]:
    """Normalize Metabase list responses (plain list or ``{"data": [...]}``)."""
    if isinstance(response, dict):
        return list(response.get("data", []))
    return list(response)


def prune_sample_content(client: MetabaseClient) -> None:
    """Remove Metabase's bundled sample content for a clean, reproducible instance.

    Metabase ships a "Sample Database" (flagged ``is_sample``) and an "Examples"
    collection (also ``is_sample``) holding the "E-commerce Insights" dashboard.
    Deleting the database does not cascade to that collection, so this also archives
    the sample collections and their dashboards. Idempotent: does nothing when the
    sample content is already gone, and tolerates failures so it never blocks the
    rest of provisioning.
    """
    for database in _as_list(client.request("GET", "/database")):
        if not database.get("is_sample"):
            continue
        database_id = int(database["id"])
        try:
            client.request("DELETE", f"/database/{database_id}")
            print(f"Removed Metabase sample database id={database_id}")
        except requests.RequestException as exc:
            print(f"Could not remove sample database id={database_id}: {exc}")

    sample_collection_ids = {
        collection["id"]
        for collection in _as_list(client.request("GET", "/collection"))
        if collection.get("is_sample")
    }
    if not sample_collection_ids:
        return

    for dashboard in _as_list(client.request("GET", "/dashboard")):
        if dashboard.get("collection_id") not in sample_collection_ids:
            continue
        dashboard_id = int(dashboard["id"])
        try:
            client.request("PUT", f"/dashboard/{dashboard_id}", json={"archived": True})
            print(f"Archived Metabase sample dashboard id={dashboard_id}")
        except requests.RequestException as exc:
            print(f"Could not archive sample dashboard id={dashboard_id}: {exc}")

    for collection_id in sample_collection_ids:
        try:
            client.request(
                "PUT", f"/collection/{collection_id}", json={"archived": True}
            )
            print(f"Archived Metabase sample collection id={collection_id}")
        except requests.RequestException as exc:
            print(f"Could not archive sample collection id={collection_id}: {exc}")


def ensure_database(client: MetabaseClient, settings: MetabaseSettings) -> int:
    """Register the warehouse as a Postgres data source (idempotent by name)."""
    for database in _as_list(client.request("GET", "/database")):
        if database.get("name") == metabase_config.WAREHOUSE_DATABASE_NAME:
            return int(database["id"])

    payload = {
        "name": metabase_config.WAREHOUSE_DATABASE_NAME,
        "engine": "postgres",
        "details": {
            "host": settings.warehouse_host,
            "port": settings.warehouse_port,
            "dbname": settings.warehouse_db,
            "user": settings.metabase_warehouse_user,
            "password": settings.metabase_warehouse_password,
            "ssl": False,
        },
    }
    created = client.request_dict("POST", "/database", json=payload)
    return int(created["id"])


def ensure_collection(client: MetabaseClient) -> int:
    """Create the BI collection if it does not exist (idempotent by name)."""
    for collection in _as_list(client.request("GET", "/collection")):
        if collection.get("name") == metabase_config.COLLECTION_NAME:
            return int(collection["id"])

    payload = {
        "name": metabase_config.COLLECTION_NAME,
        "description": "Dashboards y preguntas de la plataforma de datos de pozos.",
    }
    created = client.request_dict("POST", "/collection", json=payload)
    return int(created["id"])


def _card_payload(card: Card, database_id: int, collection_id: int) -> dict[str, Any]:
    return {
        "name": card.name,
        "description": card.description,
        "display": card.display,
        "visualization_settings": card.visualization_settings(),
        "collection_id": collection_id,
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {"query": card.sql, "template-tags": {}},
        },
    }


def ensure_card(
    client: MetabaseClient,
    card: Card,
    database_id: int,
    collection_id: int,
    existing: dict[str, int],
) -> int:
    """Create or update a single card (idempotent by name within the collection)."""
    payload = _card_payload(card, database_id, collection_id)
    if card.name in existing:
        card_id = existing[card.name]
        client.request("PUT", f"/card/{card_id}", json=payload)
        return card_id
    created = client.request_dict("POST", "/card", json=payload)
    return int(created["id"])


def ensure_dashboard(
    client: MetabaseClient, collection_id: int, card_ids: dict[str, int]
) -> int:
    """Create the dashboard and (re)attach its cards in a stable grid layout."""
    dashboard = metabase_config.DASHBOARD
    dashboard_id: int | None = None
    for existing in _as_list(client.request("GET", "/dashboard")):
        if existing.get("name") == dashboard.name:
            dashboard_id = int(existing["id"])
            break

    if dashboard_id is None:
        created = client.request_dict(
            "POST",
            "/dashboard",
            json={
                "name": dashboard.name,
                "description": dashboard.description,
                "collection_id": collection_id,
            },
        )
        dashboard_id = int(created["id"])

    dashcards = []
    row = 0
    col = 0
    for index, card_name in enumerate(dashboard.card_names):
        full_width = metabase_config.get_card(card_name).full_width
        width = GRID_WIDTH if full_width else CARD_WIDTH
        # Wrap to the next row when the card does not fit in the remaining width.
        if col + width > GRID_WIDTH:
            row += CARD_HEIGHT
            col = 0
        dashcards.append(
            {
                "id": -(index + 1),
                "card_id": card_ids[card_name],
                "row": row,
                "col": col,
                "size_x": width,
                "size_y": CARD_HEIGHT,
            }
        )
        col += width
        if col >= GRID_WIDTH:
            row += CARD_HEIGHT
            col = 0

    client.request("PUT", f"/dashboard/{dashboard_id}", json={"dashcards": dashcards})
    return dashboard_id


def provision() -> int:
    """Run the full idempotent provisioning flow. Returns the dashboard id."""
    settings = settings_from_env()
    client = MetabaseClient(settings)

    client.wait_until_healthy()
    client.authenticate()

    prune_sample_content(client)

    database_id = ensure_database(client, settings)
    collection_id = ensure_collection(client)

    existing_cards = {
        card["name"]: int(card["id"])
        for card in _as_list(client.request("GET", "/card"))
        if card.get("collection_id") == collection_id
    }

    card_ids: dict[str, int] = {}
    for card in metabase_config.CARDS:
        card_ids[card.name] = ensure_card(
            client, card, database_id, collection_id, existing_cards
        )

    dashboard_id = ensure_dashboard(client, collection_id, card_ids)

    print(
        f"Provisioned database id={database_id}, collection id={collection_id}, "
        f"{len(card_ids)} cards, dashboard id={dashboard_id} "
        f"at {settings.base_url}/dashboard/{dashboard_id}"
    )
    return dashboard_id


def main() -> int:
    """Entry point for ``python -m data_platform.bi.provision``."""
    try:
        provision()
    except (requests.RequestException, RuntimeError, KeyError) as exc:
        print(f"Provisioning failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
