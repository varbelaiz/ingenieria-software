"""Contract tests for Phase 3 prediction and model metadata endpoints."""

import pytest

from fastapi.testclient import TestClient
from app.main import app
from app.predictions import routes
from ml.inference.service import BaselinePredictionService
from tests import TEST_API_KEY


client = TestClient(app)
VALID_HEADERS = {"X-API-Key": TEST_API_KEY}


@pytest.fixture(autouse=True)
def use_baseline_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep PR 4 contract tests independent from live ML infrastructure."""

    monkeypatch.setattr(
        routes,
        "prediction_service",
        BaselinePredictionService(),
    )


def test_create_prediction_returns_stable_baseline_contract() -> None:
    """A valid request should return prediction, model, and feature metadata."""
    response = client.post(
        "/api/v1/predictions",
        json={
            "well_id": "POZO-001",
            "as_of_date": "2026-04-01",
            "horizon_days": 30,
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "well_id": "POZO-001",
        "as_of_date": "2026-04-01",
        "horizon_days": 30,
        "prediction": 975.0,
        "model": {
            "name": "deterministic-decline-baseline",
            "version": "baseline-v1",
            "run_id": None,
            "alias": "baseline",
            "metrics": {},
        },
        "features": {"feature_as_of_date": "2026-04-01"},
    }


def test_get_current_model_returns_baseline_metadata() -> None:
    """The diagnostic endpoint should describe the currently served baseline."""
    response = client.get("/api/v1/models/current", headers=VALID_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "name": "deterministic-decline-baseline",
        "version": "baseline-v1",
        "run_id": None,
        "alias": "baseline",
        "metrics": {},
    }


def test_create_prediction_requires_authentication() -> None:
    """Prediction requests should pass through the existing API-key middleware."""
    response = client.post(
        "/api/v1/predictions",
        json={
            "well_id": "POZO-001",
            "as_of_date": "2026-04-01",
            "horizon_days": 30,
        },
    )

    assert response.status_code == 403


def test_create_prediction_returns_404_for_unknown_well() -> None:
    """An unknown well should produce a controlled not-found response."""
    response = client.post(
        "/api/v1/predictions",
        json={
            "well_id": "POZO-999",
            "as_of_date": "2026-04-01",
            "horizon_days": 30,
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No features found for well POZO-999"


def test_create_prediction_rejects_non_positive_horizon() -> None:
    """Prediction horizon should be a positive number of days."""
    response = client.post(
        "/api/v1/predictions",
        json={
            "well_id": "POZO-001",
            "as_of_date": "2026-04-01",
            "horizon_days": 0,
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 422
