"""Shared configuration for the Phase 3 ML Engineering stack."""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class MLSettings:
    """Runtime settings shared by training, registry, features, and inference."""

    mlflow_tracking_uri: str
    mlflow_experiment_name: str
    mlflow_model_name: str
    feature_store_schema: str


def get_ml_settings() -> MLSettings:
    """Load ML settings from environment variables with local defaults."""

    return MLSettings(
        mlflow_tracking_uri=getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        mlflow_experiment_name=getenv(
            "MLFLOW_EXPERIMENT_NAME",
            "well-production-forecast",
        ),
        mlflow_model_name=getenv("MLFLOW_MODEL_NAME", "well-production-forecast"),
        feature_store_schema=getenv("ML_FEATURE_STORE_SCHEMA", "ml_features"),
    )
