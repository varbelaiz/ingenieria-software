"""Inference service contracts and the deterministic Phase 3 baseline."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ml.features.store import FeatureNotFoundError, FeatureStore
from ml.registry.client import RegistryReader


BASE_PRODUCTION_BY_WELL = {
    "POZO-001": 1200.0,
    "POZO-002": 980.0,
    "POZO-003": 760.0,
}
DECLINE_PER_DAY = 7.5


class FeaturesNotFoundError(LookupError):
    """Raised when inference features are unavailable for a requested well."""


@dataclass(frozen=True)
class ModelMetadata:
    """Stable metadata exposed for the model currently serving predictions."""

    name: str
    version: str
    run_id: str | None
    alias: str
    metrics: dict[str, float]


@dataclass(frozen=True)
class PredictionResult:
    """A numeric prediction and the data/model metadata used to produce it."""

    value: float
    feature_as_of_date: date
    model: ModelMetadata


class PredictionService(Protocol):
    """Boundary implemented by both baseline and registry-backed inference."""

    def predict(
        self, *, well_id: str, as_of_date: date, horizon_days: int
    ) -> PredictionResult:
        """Return one production prediction for the requested horizon."""

    def current_model(self) -> ModelMetadata:
        """Describe the model currently used for inference."""


class BaselinePredictionService:
    """Deterministic decline baseline used until PR 6 connects the registry."""

    _metadata = ModelMetadata(
        name="deterministic-decline-baseline",
        version="baseline-v1",
        run_id=None,
        alias="baseline",
        metrics={},
    )

    def predict(
        self, *, well_id: str, as_of_date: date, horizon_days: int
    ) -> PredictionResult:
        """Apply the existing linear decline convention to a known well."""

        try:
            base_production = BASE_PRODUCTION_BY_WELL[well_id]
        except KeyError as error:
            raise FeaturesNotFoundError(
                f"No features found for well {well_id}"
            ) from error

        value = max(base_production - (DECLINE_PER_DAY * horizon_days), 0.0)
        return PredictionResult(
            value=round(value, 2),
            feature_as_of_date=as_of_date,
            model=self._metadata,
        )

    def current_model(self) -> ModelMetadata:
        """Return stable metadata for the temporary baseline."""

        return self._metadata


class RegistryPredictionService:
    """Inference implementation backed by persisted features and champion model."""

    def __init__(
        self,
        *,
        feature_store: FeatureStore,
        registry: RegistryReader,
    ) -> None:
        self._feature_store = feature_store
        self._registry = registry

    def predict(
        self, *, well_id: str, as_of_date: date, horizon_days: int
    ) -> PredictionResult:
        """Predict recursively in monthly steps using point-in-time features."""

        try:
            features = self._feature_store.get_features(well_id, as_of_date)
        except FeatureNotFoundError as error:
            raise FeaturesNotFoundError(
                f"No features found for well {well_id}"
            ) from error

        champion = self._registry.load_champion()
        value = float(features.gas_production_current)
        monthly_steps = max(1, (horizon_days + 29) // 30)
        for _ in range(monthly_steps):
            value = champion.model.predict(value)

        metadata = champion.metadata
        return PredictionResult(
            value=round(max(value, 0.0), 2),
            feature_as_of_date=features.as_of_date,
            model=ModelMetadata(
                name=metadata.name,
                version=metadata.version,
                run_id=metadata.run_id,
                alias=metadata.alias,
                metrics=metadata.metrics,
            ),
        )

    def current_model(self) -> ModelMetadata:
        """Resolve fresh champion metadata for the diagnostic endpoint."""

        metadata = self._registry.load_champion().metadata
        return ModelMetadata(
            name=metadata.name,
            version=metadata.version,
            run_id=metadata.run_id,
            alias=metadata.alias,
            metrics=metadata.metrics,
        )
