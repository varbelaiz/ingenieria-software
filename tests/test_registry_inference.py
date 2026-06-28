"""Integration tests for promoted-model inference over feature-store rows."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.predictions import routes
from ml.features.store import FeatureRow, FeatureStore, InMemoryFeatureRepository
from ml.inference.service import RegistryPredictionService
from ml.registry.client import RegisteredModel, ResolvedModel
from ml.registry.errors import NoPromotedModelError
from ml.training.train import LinearModel
from tests import TEST_API_KEY


client = TestClient(app)
VALID_HEADERS = {"X-API-Key": TEST_API_KEY}


def _feature_row() -> FeatureRow:
    return FeatureRow(
        well_id="POZO-001",
        as_of_date=date(2024, 3, 1),
        gas_production_current=Decimal("100"),
        gas_production_avg_3m=Decimal("100"),
        gas_production_avg_6m=Decimal("100"),
        gas_production_trend_3m=Decimal("0"),
        oil_production_current=Decimal("10"),
        water_production_current=Decimal("5"),
        producing_days_available=30,
        production_months_available=3,
        formation="Vaca Muerta",
        basin="Neuquina",
        resource_type="Shale",
    )


def test_registry_inference_uses_champion_and_exposes_traceability() -> None:
    champion = RegisteredModel(
        name="gas-forecast",
        version="4",
        run_id="run-4",
        alias="champion",
        metrics={"mae": 2.5, "rmse": 3.0},
    )

    class Registry:
        def load_champion(self) -> ResolvedModel:
            return ResolvedModel(
                metadata=champion,
                model=LinearModel(
                    slope=0.9,
                    intercept=0.0,
                    feature_names=("gas_production_current",),
                ),
            )

    service = RegistryPredictionService(
        feature_store=FeatureStore(InMemoryFeatureRepository([_feature_row()])),
        registry=Registry(),
    )

    result = service.predict(
        well_id="POZO-001",
        as_of_date=date(2024, 3, 15),
        horizon_days=30,
    )

    assert result.value == 90.0
    assert result.feature_as_of_date == date(2024, 3, 1)
    assert result.model.version == "4"
    assert result.model.run_id == "run-4"
    assert result.model.metrics == {"mae": 2.5, "rmse": 3.0}


def test_registry_inference_fails_clearly_without_champion() -> None:
    class Registry:
        def load_champion(self) -> ResolvedModel:
            raise NoPromotedModelError("No champion model is registered")

    service = RegistryPredictionService(
        feature_store=FeatureStore(InMemoryFeatureRepository([_feature_row()])),
        registry=Registry(),
    )

    with pytest.raises(NoPromotedModelError, match="No champion"):
        service.predict(
            well_id="POZO-001",
            as_of_date=date(2024, 3, 15),
            horizon_days=30,
        )


def test_prediction_api_returns_promoted_model_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    champion = RegisteredModel(
        name="gas-forecast",
        version="4",
        run_id="run-4",
        alias="champion",
        metrics={"mae": 2.5},
    )

    class Registry:
        def load_champion(self) -> ResolvedModel:
            return ResolvedModel(
                metadata=champion,
                model=LinearModel(
                    slope=0.9,
                    intercept=0.0,
                    feature_names=("gas_production_current",),
                ),
            )

    service = RegistryPredictionService(
        feature_store=FeatureStore(InMemoryFeatureRepository([_feature_row()])),
        registry=Registry(),
    )
    monkeypatch.setattr(routes, "prediction_service", service)

    response = client.post(
        "/api/v1/predictions",
        json={
            "well_id": "POZO-001",
            "as_of_date": "2024-03-15",
            "horizon_days": 30,
        },
        headers=VALID_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["model"] == {
        "name": "gas-forecast",
        "version": "4",
        "run_id": "run-4",
        "alias": "champion",
        "metrics": {"mae": 2.5},
    }


def test_current_model_api_returns_503_without_champion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Registry:
        def load_champion(self) -> ResolvedModel:
            raise NoPromotedModelError("No champion model is registered")

    service = RegistryPredictionService(
        feature_store=FeatureStore(InMemoryFeatureRepository([_feature_row()])),
        registry=Registry(),
    )
    monkeypatch.setattr(routes, "prediction_service", service)

    response = client.get("/api/v1/models/current", headers=VALID_HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"] == "No champion model is registered"
