"""Tests for Prometheus metrics exposure and basic HTTP instrumentation."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
VALID_HEADERS = {"X-API-Key": "abcdef12345"}


def test_metrics_endpoint_is_exposed_without_api_key() -> None:
    """The Prometheus scrape endpoint should be reachable without API auth."""
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "forecast_api_requests_total" in response.text
    assert "process_resident_memory_bytes" in response.text


def test_forecast_request_is_recorded_in_metrics() -> None:
    """A forecast request should update request count, latency, and error metrics."""
    client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-001",
            "date_start": "2026-04-01",
            "date_end": "2026-04-03",
        },
        headers=VALID_HEADERS,
    )
    response = client.get("/metrics")

    assert response.status_code == 200
    assert (
        'forecast_api_requests_total{method="GET",path="/api/v1/forecast",status_code="200"}'
        in response.text
    )
    assert (
        'forecast_api_request_duration_seconds_count{method="GET",path="/api/v1/forecast",status_code="200"}'
        in response.text
    )


def test_http_errors_are_recorded_in_metrics() -> None:
    """A failing request should be reflected by the error counter."""
    client.get("/api/v1/wells", params={"date_query": "2026-04-28"})
    response = client.get("/metrics")

    assert response.status_code == 200
    assert (
        'forecast_api_errors_total{method="GET",path="/api/v1/wells",status_code="403"}'
        in response.text
    )
