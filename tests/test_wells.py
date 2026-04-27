"""Tests for wells endpoint behavior and validations."""

from fastapi.testclient import TestClient

from app.main import app
from tests import TEST_API_KEY


client = TestClient(app)
VALID_HEADERS = {"X-API-Key": TEST_API_KEY}


def test_get_wells_returns_200_with_expected_json_structure() -> None:
    """It should return 200 and the expected wells payload."""
    response = client.get(
        "/api/v1/wells", params={"date_query": "2026-04-28"}, headers=VALID_HEADERS
    )

    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)
    assert payload == [
        {"id_well": "POZO-001"},
        {"id_well": "POZO-002"},
        {"id_well": "POZO-003"},
    ]


def test_get_wells_returns_422_when_missing_date_query() -> None:
    """It should return 422 when required date_query is missing."""
    response = client.get("/api/v1/wells", headers=VALID_HEADERS)

    assert response.status_code == 422


def test_get_wells_returns_422_when_date_query_has_invalid_format() -> None:
    """It should return 422 when date_query does not use YYYY-MM-DD format."""
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "28-04-2026"},
        headers=VALID_HEADERS,
    )

    assert response.status_code == 422
