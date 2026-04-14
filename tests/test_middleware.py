"""Tests for the global API key authentication middleware."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_returns_403_without_api_key() -> None:
    """It should return 403 when API key header is missing."""
    response = client.get("/api/v1/wells", params={"date_query": "2026-04-28"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing API key"


def test_returns_403_with_invalid_api_key() -> None:
    """It should return 403 when API key header is invalid."""
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2026-04-28"},
        headers={"X-API-Key": "invalid-key"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing API key"


def test_healthz_is_exposed_without_api_key() -> None:
    """It should expose the technical health check without authentication."""
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_is_hidden_from_openapi_schema() -> None:
    """It should keep the technical health check out of the public schema."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/healthz" not in response.json()["paths"]
