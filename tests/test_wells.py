from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
VALID_HEADERS = {"X-API-Key": "abcdef12345"}


def test_get_wells_returns_200_with_expected_json_structure() -> None:
    response = client.get("/api/v1/wells", params={"date_query": "2026-04-28"}, headers=VALID_HEADERS)

    assert response.status_code == 200

    payload = response.json()
    assert payload["date_query"] == "2026-04-28"
    assert isinstance(payload["wells"], list)
    assert payload["wells"] == ["POZO-001", "POZO-002", "POZO-003"]


def test_get_wells_returns_403_without_api_key() -> None:
    response = client.get("/api/v1/wells", params={"date_query": "2026-04-28"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing API key"


def test_get_wells_returns_403_with_invalid_api_key() -> None:
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2026-04-28"},
        headers={"X-API-Key": "invalid-key"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing API key"


def test_get_wells_returns_422_when_missing_date_query() -> None:
    response = client.get("/api/v1/wells", headers=VALID_HEADERS)

    assert response.status_code == 422


def test_get_wells_returns_422_when_date_query_has_invalid_format() -> None:
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "28-04-2026"},
        headers=VALID_HEADERS,
    )

    assert response.status_code == 422
