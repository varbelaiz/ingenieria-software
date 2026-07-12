"""REST contract for Phase 3 model predictions and diagnostics."""

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml.inference.service import (
    BaselinePredictionService,
    FeaturesNotFoundError,
    ModelMetadata,
    PredictionService,
)


router = APIRouter(prefix="/api/v1", tags=["predictions"])
prediction_service: PredictionService = BaselinePredictionService()


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

    return _model_response(prediction_service.current_model())
