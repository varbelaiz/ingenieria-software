"""MLflow Model Registry helpers with explicit candidate/champion aliases."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

from ml.config import get_ml_settings
from ml.registry.errors import NoPromotedModelError
from ml.training.train import LinearModel


@dataclass(frozen=True)
class RegisteredModel:
    """Traceable model-version metadata used by promotion and inference."""

    name: str
    version: str
    run_id: str
    alias: str
    metrics: dict[str, float]


@dataclass(frozen=True)
class ResolvedModel:
    """Registered metadata paired with a locally loaded prediction model."""

    metadata: RegisteredModel
    model: LinearModel


class RegistryReader(Protocol):
    """Inference-facing registry boundary."""

    def load_champion(self) -> ResolvedModel:
        """Resolve champion metadata and deserialize its model artifact."""


class MLflowRegistryClient:
    """Small adapter around MLflow's version and alias APIs."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        model_name: str | None = None,
    ) -> None:
        self._client = client
        self._model_name = model_name or get_ml_settings().mlflow_model_name

    @property
    def client(self) -> Any:
        """Construct the MLflow client lazily for import-safe unit tests."""

        if self._client is None:
            from mlflow import MlflowClient  # pylint: disable=import-outside-toplevel

            self._client = MlflowClient(
                tracking_uri=get_ml_settings().mlflow_tracking_uri
            )
        return self._client

    def register_run_model(self, run_id: str) -> RegisteredModel:
        """Register a run's JSON artifact and mark the version as candidate."""

        try:
            self.client.create_registered_model(self._model_name)
        except Exception as error:  # pylint: disable=broad-exception-caught
            if getattr(error, "error_code", None) != "RESOURCE_ALREADY_EXISTS":
                raise

        source = f"runs:/{run_id}/model/model.json"
        model_version = self.client.create_model_version(
            name=self._model_name,
            source=source,
            run_id=run_id,
        )
        version = str(model_version.version)
        self.client.set_registered_model_alias(
            self._model_name,
            "candidate",
            version,
        )
        return self._registered_model(model_version, alias="candidate")

    def get_champion(self) -> RegisteredModel | None:
        """Return current champion metadata, or ``None`` when absent."""

        try:
            version = self.client.get_model_version_by_alias(
                self._model_name,
                "champion",
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            missing_codes = {"RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"}
            if getattr(error, "error_code", None) not in missing_codes:
                raise
            return None
        return self._registered_model(version, alias="champion")

    def set_champion(self, version: str) -> None:
        """Atomically move the champion alias to a validated version."""

        self.client.set_registered_model_alias(
            self._model_name,
            "champion",
            version,
        )

    def load_champion(self) -> ResolvedModel:
        """Download and deserialize the champion run's JSON model artifact."""

        champion = self.get_champion()
        if champion is None:
            raise NoPromotedModelError("No champion model is registered")

        local_path = self.client.download_artifacts(
            champion.run_id,
            "model/model.json",
        )
        payload = json.loads(Path(local_path).read_text(encoding="utf-8"))
        return ResolvedModel(
            metadata=champion,
            model=LinearModel(
                slope=float(payload["slope"]),
                intercept=float(payload["intercept"]),
                feature_names=tuple(payload["feature_names"]),
            ),
        )

    def _registered_model(self, version: Any, *, alias: str) -> RegisteredModel:
        run_id = str(version.run_id)
        run = self.client.get_run(run_id)
        metrics = {str(name): float(value) for name, value in run.data.metrics.items()}
        return RegisteredModel(
            name=self._model_name,
            version=str(version.version),
            run_id=run_id,
            alias=alias,
            metrics=metrics,
        )
