"""REST contract for Phase 3 model predictions and diagnostics."""

from datetime import date
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml.inference.service import (
    BaselinePredictionService,
    FeaturesNotFoundError,
    ModelMetadata,
    PredictionService,
    RegistryPredictionService,
)
from ml.features.store import FeatureStore, PostgresFeatureRepository
from ml.registry.client import MLflowRegistryClient
from ml.registry.errors import NoPromotedModelError


router = APIRouter(prefix="/api/v1", tags=["predictions"])


def _warehouse_connection() -> Any:
    """Open Postgres lazily so app startup does not require a live warehouse."""

    import psycopg2  # pylint: disable=import-outside-toplevel,import-error

    return psycopg2.connect(
        host=os.getenv("WAREHOUSE_HOST", "localhost"),
        port=int(os.getenv("WAREHOUSE_PORT", "5432")),
        user=os.getenv("WAREHOUSE_USER", "warehouse"),
        password=os.getenv("WAREHOUSE_PASSWORD", "warehouse"),
        dbname=os.getenv("WAREHOUSE_DB", "warehouse"),
    )


def _build_prediction_service() -> PredictionService:
    if os.getenv("ML_INFERENCE_BACKEND", "registry") == "baseline":
        return BaselinePredictionService()
    return RegistryPredictionService(
        feature_store=FeatureStore(PostgresFeatureRepository(_warehouse_connection)),
        registry=MLflowRegistryClient(),
    )


prediction_service: PredictionService = _build_prediction_service()


class PredictionRequest(BaseModel):
    """Input required to produce a point-in-time well prediction."""

    well_id: str = Field(min_length=1)
    as_of_date: date
    horizon_days: int = Field(gt=0, le=365)


class ModelMetadataResponse(BaseModel):
    """Public metadata for the model serving a prediction."""

    name: str
    version: str
    run_id: str | None
    alias: str
    metrics: dict[str, float]


class FeatureMetadataResponse(BaseModel):
    """Point-in-time metadata for the features used by inference."""

    feature_as_of_date: date


class PredictionResponse(BaseModel):
    """Stable response contract shared by baseline and registry inference."""

    well_id: str
    as_of_date: date
    horizon_days: int
    prediction: float
    model: ModelMetadataResponse
    features: FeatureMetadataResponse


def _model_response(metadata: ModelMetadata) -> ModelMetadataResponse:
    return ModelMetadataResponse(
        name=metadata.name,
        version=metadata.version,
        run_id=metadata.run_id,
        alias=metadata.alias,
        metrics=metadata.metrics,
    )


@router.post("/predictions", response_model=PredictionResponse)
def create_prediction(request: PredictionRequest) -> PredictionResponse:
    """Return a production prediction with traceable model/feature metadata."""

    try:
        result = prediction_service.predict(
            well_id=request.well_id,
            as_of_date=request.as_of_date,
            horizon_days=request.horizon_days,
        )
    except FeaturesNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except NoPromotedModelError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return PredictionResponse(
        well_id=request.well_id,
        as_of_date=request.as_of_date,
        horizon_days=request.horizon_days,
        prediction=result.value,
        model=_model_response(result.model),
        features=FeatureMetadataResponse(feature_as_of_date=result.feature_as_of_date),
    )


@router.get("/models/current", response_model=ModelMetadataResponse)
def get_current_model() -> ModelMetadataResponse:
    """Describe the model currently serving prediction requests."""

    try:
        return _model_response(prediction_service.current_model())
    except NoPromotedModelError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
