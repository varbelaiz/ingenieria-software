"""Synthetic traffic profiles implemented with Locust."""

from __future__ import annotations

import random
from threading import Lock
from typing import Any

from locust import HttpUser, constant, events, task

try:
    from traffic_config import (
        DEFAULT_WAIT_TIME_SECONDS,
        FORECAST_END,
        FORECAST_START,
        Scenario,
        TRAFFIC_WEIGHTS,
        VALID_WELL_IDS,
        build_seed_scenarios,
        resolve_api_key,
        resolve_locust_host,
        summarize_body,
    )
except ModuleNotFoundError:
    from load.traffic_config import (
        DEFAULT_WAIT_TIME_SECONDS,
        FORECAST_END,
        FORECAST_START,
        Scenario,
        TRAFFIC_WEIGHTS,
        VALID_WELL_IDS,
        build_seed_scenarios,
        resolve_api_key,
        resolve_locust_host,
        summarize_body,
    )


API_KEY = resolve_api_key()
SEED_SCENARIOS = build_seed_scenarios(API_KEY)
_SEED_LOCK = Lock()
_SEED_STATE: dict[str, bool] = {"completed": False}


@events.test_start.add_listener
def reset_seed_state(environment: Any, **kwargs: Any) -> None:
    """Reset one-time monitoring seed state between Locust test runs."""
    del environment, kwargs
    _SEED_STATE["completed"] = False


def _request_name(scenario_name: str, path: str) -> str:
    """Return a readable request label in Locust statistics."""
    return f"{scenario_name} {path}"


def _build_failure_message(
    scenario_name: str,
    expected_status: int,
    actual_status: int,
    response_body: str,
) -> str:
    """Create a compact failure message for unexpected responses."""
    return (
        f"{scenario_name} expected status {expected_status}, "
        f"got {actual_status}; body={summarize_body(response_body)}"
    )


def _perform_scenario(client: Any, scenario: Scenario) -> None:
    """Execute one GET request and validate the expected status code."""
    with client.get(
        scenario.path,
        params=scenario.params,
        headers={"X-API-Key": scenario.api_key},
        name=_request_name(scenario.name, scenario.path),
        catch_response=True,
    ) as response:
        if response.status_code == scenario.expected_status:
            response.success()
            return

        response.failure(
            _build_failure_message(
                scenario.name,
                scenario.expected_status,
                response.status_code,
                response.text,
            )
        )


def _seed_monitoring_once(client: Any) -> None:
    """Generate a short deterministic burst so dashboard error panels appear."""
    if _SEED_STATE["completed"]:
        return

    with _SEED_LOCK:
        if _SEED_STATE["completed"]:
            return

        for scenario in SEED_SCENARIOS:
            _perform_scenario(client, scenario)

        _SEED_STATE["completed"] = True


def _call_wells_ok(client: Any) -> None:
    _perform_scenario(
        client,
        SEED_SCENARIOS[0],
    )


def _call_forecast_ok(client: Any) -> None:
    _perform_scenario(
        client,
        Scenario(
            name="forecast_ok",
            path="/api/v1/forecast",
            params={
                "id_well": random.choice(VALID_WELL_IDS),
                "date_start": FORECAST_START,
                "date_end": FORECAST_END,
            },
            api_key=API_KEY,
            expected_status=200,
        ),
    )


def _call_forbidden_key(client: Any) -> None:
    _perform_scenario(
        client,
        SEED_SCENARIOS[2],
    )


def _call_forecast_not_found(client: Any) -> None:
    _perform_scenario(
        client,
        SEED_SCENARIOS[3],
    )


class BaseTrafficUser(HttpUser):
    """Shared Locust user base with one-time dashboard seeding."""

    abstract = True
    host = resolve_locust_host()
    wait_time = constant(DEFAULT_WAIT_TIME_SECONDS)

    def on_start(self) -> None:
        """Populate the monitoring seed once before this user starts looping."""
        _seed_monitoring_once(self.client)


class MonitoringTrafficUser(BaseTrafficUser):
    """Weighted traffic mix shared by UI, normal and intense presets."""

    @task(TRAFFIC_WEIGHTS["forecast_ok"])
    def forecast_ok(self) -> None:
        """Request a valid forecast for a random well."""
        _call_forecast_ok(self.client)

    @task(TRAFFIC_WEIGHTS["wells_ok"])
    def wells_ok(self) -> None:
        """Request the well listing with a valid API key."""
        _call_wells_ok(self.client)

    @task(TRAFFIC_WEIGHTS["forbidden_key"])
    def forbidden_key(self) -> None:
        """Exercise the expected 403 path with an invalid API key."""
        _call_forbidden_key(self.client)

    @task(TRAFFIC_WEIGHTS["forecast_not_found"])
    def forecast_not_found(self) -> None:
        """Exercise the expected 404 path for an unknown well."""
        _call_forecast_not_found(self.client)
