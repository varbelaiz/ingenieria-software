"""Shared configuration helpers for synthetic traffic generation."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_LOCUST_HOST = "http://127.0.0.1:8000"
DEFAULT_API_KEY = "api_key"
INVALID_API_KEY = "invalid-key"
DEFAULT_WAIT_TIME_SECONDS = 0.4

VALID_WELL_IDS = ("POZO-001", "POZO-002", "POZO-003")
WELL_DATE = "2026-03-25"
FORECAST_START = "2026-03-25"
FORECAST_END = "2026-03-27"
TRAFFIC_WEIGHTS = {
    "forecast_ok": 75,
    "wells_ok": 18,
    "forbidden_key": 4,
    "forecast_not_found": 3,
}


@dataclass(frozen=True)
class Scenario:
    """Describe a single HTTP request sent by Locust."""

    name: str
    path: str
    params: dict[str, str]
    api_key: str
    expected_status: int


def read_env(name: str, default: str) -> str:
    """Return an environment variable or a non-empty default value."""
    value = os.getenv(name, default).strip()
    return value or default


def resolve_locust_host() -> str:
    """Resolve the target host used by the Locust user class."""
    locust_host = os.getenv("LOCUST_HOST")
    if locust_host and locust_host.strip():
        return locust_host.strip()

    return read_env("API_BASE_URL", DEFAULT_LOCUST_HOST)


def resolve_api_key() -> str:
    """Resolve the API key used for successful requests."""
    return read_env("API_KEY", DEFAULT_API_KEY)


def build_seed_scenarios(api_key: str) -> tuple[Scenario, ...]:
    """Return the deterministic request burst used to seed monitoring panels."""
    return (
        Scenario(
            name="wells_ok",
            path="/api/v1/wells",
            params={"date_query": WELL_DATE},
            api_key=api_key,
            expected_status=200,
        ),
        Scenario(
            name="forecast_ok",
            path="/api/v1/forecast",
            params={
                "id_well": VALID_WELL_IDS[0],
                "date_start": FORECAST_START,
                "date_end": FORECAST_END,
            },
            api_key=api_key,
            expected_status=200,
        ),
        Scenario(
            name="forbidden_key",
            path="/api/v1/wells",
            params={"date_query": WELL_DATE},
            api_key=INVALID_API_KEY,
            expected_status=403,
        ),
        Scenario(
            name="forecast_not_found",
            path="/api/v1/forecast",
            params={
                "id_well": "POZO-999",
                "date_start": FORECAST_START,
                "date_end": FORECAST_END,
            },
            api_key=api_key,
            expected_status=404,
        ),
    )


def summarize_body(body: str, limit: int = 160) -> str:
    """Collapse whitespace and shorten response bodies for failure messages."""
    normalized = " ".join(body.split())
    if not normalized:
        return "<empty>"

    if len(normalized) <= limit:
        return normalized

    return normalized[: limit - 3] + "..."
