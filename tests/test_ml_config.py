"""Tests for the shared ML Engineering configuration."""

import pytest

from ml.config import MLSettings, get_ml_settings


def test_get_ml_settings_uses_phase3_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return the shared Phase 3 defaults when no env vars are set."""

    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.delenv("MLFLOW_EXPERIMENT_NAME", raising=False)
    monkeypatch.delenv("MLFLOW_MODEL_NAME", raising=False)
    monkeypatch.delenv("ML_FEATURE_STORE_SCHEMA", raising=False)

    settings = get_ml_settings()

    assert settings == MLSettings(
        mlflow_tracking_uri="http://localhost:5000",
        mlflow_experiment_name="well-production-forecast",
        mlflow_model_name="well-production-forecast",
        feature_store_schema="ml_features",
    )


def test_get_ml_settings_allows_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow local and CI environments to override ML settings."""

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.local:5000")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "custom-experiment")
    monkeypatch.setenv("MLFLOW_MODEL_NAME", "custom-model")
    monkeypatch.setenv("ML_FEATURE_STORE_SCHEMA", "custom_features")

    settings = get_ml_settings()

    assert settings.mlflow_tracking_uri == "http://mlflow.local:5000"
    assert settings.mlflow_experiment_name == "custom-experiment"
    assert settings.mlflow_model_name == "custom-model"
    assert settings.feature_store_schema == "custom_features"
