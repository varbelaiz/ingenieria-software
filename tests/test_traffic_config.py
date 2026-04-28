"""Unit tests for Locust traffic configuration helpers."""

import pytest

from load import traffic_config


def test_resolve_locust_host_prefers_locust_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LOCUST_HOST should win over the legacy API_BASE_URL fallback."""
    monkeypatch.setenv("LOCUST_HOST", "https://locust.example.com")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")

    assert traffic_config.resolve_locust_host() == "https://locust.example.com"


def test_resolve_locust_host_falls_back_to_api_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API_BASE_URL should still work as an internal fallback."""
    monkeypatch.delenv("LOCUST_HOST", raising=False)
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")

    assert traffic_config.resolve_locust_host() == "https://api.example.com"


def test_build_seed_scenarios_contains_expected_statuses() -> None:
    """The monitoring seed should always cover the four expected outcomes."""
    scenarios = traffic_config.build_seed_scenarios("api_key")

    assert [scenario.name for scenario in scenarios] == [
        "wells_ok",
        "forecast_ok",
        "forbidden_key",
        "forecast_not_found",
    ]
    assert [scenario.expected_status for scenario in scenarios] == [
        200,
        200,
        403,
        404,
    ]


def test_build_seed_scenarios_uses_invalid_key_for_forbidden_case() -> None:
    """The 403 seed request should always use the invalid API key."""
    scenarios = traffic_config.build_seed_scenarios("api_key")

    assert scenarios[2].api_key == traffic_config.INVALID_API_KEY


def test_summarize_body_collapses_whitespace_and_truncates() -> None:
    """Failure messages should stay short and readable."""
    body = " error\n\n detail   " + ("x" * 200)

    summary = traffic_config.summarize_body(body, limit=30)

    assert summary == "error detail xxxxxxxxxxxxxx..."
