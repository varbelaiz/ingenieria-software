from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
VALID_HEADERS = {"X-API-Key": "abcdef12345"}


def test_get_forecast_returns_200_with_expected_json_structure():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-001",
            "date_start": "2026-04-01",
            "date_end": "2026-04-03",
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["id_well"] == "POZO-001"
    assert payload["date_start"] == "2026-04-01"
    assert payload["date_end"] == "2026-04-03"
    assert payload["trend"] == "linear_decreasing"
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) == 3
    assert payload["data"][0] == {"date": "2026-04-01", "oil_bopd": 1200.0}
    assert payload["data"][1] == {"date": "2026-04-02", "oil_bopd": 1192.5}


def test_get_forecast_returns_403_without_api_key():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-001",
            "date_start": "2026-04-01",
            "date_end": "2026-04-03",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing API key"


def test_get_forecast_returns_400_when_date_end_before_date_start():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-001",
            "date_start": "2026-04-10",
            "date_end": "2026-04-01",
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "date_end debe ser mayor o igual a date_start"


def test_get_forecast_returns_422_when_missing_required_parameter():
    response = client.get(
        "/api/v1/forecast",
        params={
            "date_start": "2026-04-01",
            "date_end": "2026-04-03",
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 422


def test_get_forecast_returns_403_with_invalid_api_key():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-001",
            "date_start": "2026-04-01",
            "date_end": "2026-04-03",
        },
        headers={"X-API-Key": "invalid-key"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing API key"


def test_get_forecast_returns_404_for_unknown_well():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-999",
            "date_start": "2026-04-01",
            "date_end": "2026-04-03",
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Pozo no encontrado"


def test_get_forecast_returns_422_when_date_format_is_invalid():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-001",
            "date_start": "01-04-2026",
            "date_end": "2026-04-03",
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 422


def test_get_forecast_same_start_and_end_date_returns_single_point():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-002",
            "date_start": "2026-04-05",
            "date_end": "2026-04-05",
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 1
    assert payload["data"][0] == {"date": "2026-04-05", "oil_bopd": 980.0}


def test_get_forecast_long_range_never_returns_negative_production():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "POZO-003",
            "date_start": "2026-01-01",
            "date_end": "2026-06-01",
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert all(point["oil_bopd"] >= 0 for point in payload["data"])
