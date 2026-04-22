"""Generate local API traffic to validate the Grafana monitoring dashboard."""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass

import httpx

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_API_KEY = "api_key"
WELL_IDS = ("POZO-001", "POZO-002", "POZO-003")


@dataclass(frozen=True)
class Scenario:
    """Describe one HTTP request to send during traffic generation."""

    name: str
    path: str
    params: dict[str, str]
    api_key: str
    expected_status: int


def build_scenarios(api_key: str) -> list[Scenario]:
    """Return the set of scenarios used to populate monitoring metrics."""
    return [
        Scenario(
            name="wells_ok",
            path="/api/v1/wells",
            params={"date_query": "2026-03-25"},
            api_key=api_key,
            expected_status=200,
        ),
        Scenario(
            name="forecast_ok",
            path="/api/v1/forecast",
            params={
                "id_well": random.choice(WELL_IDS),
                "date_start": "2026-03-25",
                "date_end": "2026-03-27",
            },
            api_key=api_key,
            expected_status=200,
        ),
        Scenario(
            name="forbidden_key",
            path="/api/v1/wells",
            params={"date_query": "2026-03-25"},
            api_key="invalid-key",
            expected_status=403,
        ),
        Scenario(
            name="forecast_not_found",
            path="/api/v1/forecast",
            params={
                "id_well": "POZO-999",
                "date_start": "2026-03-25",
                "date_end": "2026-03-27",
            },
            api_key=api_key,
            expected_status=404,
        ),
    ]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate API traffic to populate the monitoring dashboard.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Base URL of the running API.",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="Valid API key used for successful requests.",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=5,
        help="How many scenario batches to execute.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.5,
        help="Delay between requests to create readable series in Grafana.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="HTTP client timeout for each request.",
    )
    return parser.parse_args()


def run() -> int:
    """Execute configured traffic generation scenarios."""
    args = parse_args()
    random.seed(42)
    sent_requests = 0

    with httpx.Client(base_url=args.api_url, timeout=args.timeout_seconds) as client:
        for cycle in range(1, args.cycles + 1):
            for scenario in build_scenarios(args.api_key):
                response = client.get(
                    scenario.path,
                    params=scenario.params,
                    headers={"X-API-Key": scenario.api_key},
                )
                sent_requests += 1

                print(
                    "cycle="
                    f"{cycle} scenario={scenario.name} "
                    f"status={response.status_code} "
                    f"expected={scenario.expected_status}"
                )

                if response.status_code != scenario.expected_status:
                    print(f"unexpected response body: {response.text}")
                    return 1

                time.sleep(args.pause_seconds)

    print(f"sent_requests={sent_requests}")
    print("Traffic generation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
