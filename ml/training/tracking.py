"""MLflow experiment tracking helpers for Phase 3 training workflows."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow

from ml.config import get_ml_settings


ParamValue = str | int | float | bool


@dataclass(frozen=True)
class MLflowRunMetadata:
    """Standard reproducibility metadata attached to every MLflow run."""

    as_of_date: str
    dataset_start: str
    dataset_end: str
    feature_view: str
    model_type: str
    git_sha: str | None = None

    def to_tags(self) -> dict[str, str]:
        """Return MLflow tags, omitting optional values that were not provided."""

        tags = {
            "as_of_date": self.as_of_date,
            "dataset_start": self.dataset_start,
            "dataset_end": self.dataset_end,
            "feature_view": self.feature_view,
            "model_type": self.model_type,
        }
        if self.git_sha:
            tags["git_sha"] = self.git_sha
        return tags


class TrackedRun:
    """Thin wrapper around the active MLflow run used by training code."""

    def __init__(self, active_run: Any) -> None:
        self._active_run = active_run

    @property
    def run_id(self) -> str | None:
        """Return the MLflow run id when the active run exposes one."""

        run_info = getattr(self._active_run, "info", None)
        run_id = getattr(run_info, "run_id", None)
        if run_id is None:
            return None
        return str(run_id)

    def log_params(self, params: Mapping[str, ParamValue]) -> None:
        """Log model or smoke parameters to the active run."""

        mlflow.log_params(dict(params))

    def log_metrics(
        self,
        metrics: Mapping[str, float],
        step: int | None = None,
    ) -> None:
        """Log scalar metrics to the active run."""

        mlflow.log_metrics(dict(metrics), step=step)

    def log_artifact(
        self,
        local_path: str | Path,
        artifact_path: str | None = None,
    ) -> None:
        """Log a local artifact path to the active run."""

        mlflow.log_artifact(str(local_path), artifact_path=artifact_path)


@contextmanager
def start_tracked_run(
    metadata: MLflowRunMetadata,
    run_name: str | None = None,
) -> Iterator[TrackedRun]:
    """Start an MLflow run configured with project defaults and standard tags."""

    settings = get_ml_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name=run_name) as active_run:
        mlflow.set_tags(metadata.to_tags())
        yield TrackedRun(active_run)
