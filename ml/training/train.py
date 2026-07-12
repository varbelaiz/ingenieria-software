"""Reproducible baseline training entrypoint for Phase 3."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Protocol

from ml.features.store import PostgresFeatureRepository
from ml.training.dataset import TrainingDataset, load_training_dataset


ParamValue = str | int | float | bool


class RunLogger(Protocol):
    """Minimal tracking surface consumed by the training implementation."""

    @property
    def run_id(self) -> str | None:
        """Return the backing experiment run identifier."""

    def log_params(self, params: Mapping[str, ParamValue]) -> None:
        """Log comparable training parameters."""

    def log_metrics(self, metrics: Mapping[str, float]) -> None:
        """Log scalar validation metrics."""

    def log_artifact(
        self, local_path: str | Path, artifact_path: str | None = None
    ) -> None:
        """Persist a model artifact under the run."""


@dataclass(frozen=True)
class LinearModel:
    """Single-feature ordinary least-squares regression model."""

    slope: float
    intercept: float
    feature_names: tuple[str, ...]

    def predict(self, value: float) -> float:
        """Predict next-period gas production."""

        return self.intercept + (self.slope * value)


@dataclass(frozen=True)
class TrainingResult:
    """Evidence returned after fitting and logging one model."""

    run_id: str | None
    model: LinearModel
    metrics: dict[str, float]


def fit_linear_model(
    dataset: TrainingDataset,
) -> tuple[LinearModel, dict[str, float]]:
    """Fit deterministic OLS and calculate in-sample baseline metrics."""

    x_values = [row[0] for row in dataset.features]
    y_values = list(dataset.targets)
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    variance = sum((value - x_mean) ** 2 for value in x_values)
    covariance = sum(
        (x_value - x_mean) * (y_value - y_mean)
        for x_value, y_value in zip(x_values, y_values)
    )
    slope = covariance / variance if variance else 0.0
    intercept = y_mean - (slope * x_mean)
    model = LinearModel(
        slope=round(slope, 12),
        intercept=round(intercept, 12),
        feature_names=dataset.feature_names,
    )

    errors = [
        model.predict(x_value) - y_value for x_value, y_value in zip(x_values, y_values)
    ]
    metrics = {
        "mae": round(sum(abs(error) for error in errors) / len(errors), 12),
        "rmse": round(
            math.sqrt(sum(error**2 for error in errors) / len(errors)),
            12,
        ),
        "rows": float(len(errors)),
    }
    return model, metrics


def train_dataset(
    dataset: TrainingDataset,
    *,
    run: RunLogger,
    artifact_directory: Path,
) -> TrainingResult:
    """Fit a model and record parameters, metrics, and its JSON artifact."""

    model, metrics = fit_linear_model(dataset)
    run.log_params(
        {
            "model_type": "linear_regression",
            "feature_count": len(dataset.feature_names),
        }
    )
    run.log_metrics(metrics)

    artifact_directory.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_directory / "model.json"
    artifact_path.write_text(
        json.dumps(
            {
                "model_type": "linear_regression",
                "feature_names": list(model.feature_names),
                "slope": model.slope,
                "intercept": model.intercept,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    run.log_artifact(artifact_path, artifact_path="model")
    return TrainingResult(run_id=run.run_id, model=model, metrics=metrics)


def _warehouse_connection() -> object:
    """Create a warehouse connection from the repository's standard env vars."""

    # Imported lazily so unit tests do not require the data dependency group.
    import psycopg2  # pylint: disable=import-outside-toplevel,import-error

    return psycopg2.connect(
        host=os.getenv("WAREHOUSE_HOST", "localhost"),
        port=int(os.getenv("WAREHOUSE_PORT", "5432")),
        user=os.getenv("WAREHOUSE_USER", "warehouse"),
        password=os.getenv("WAREHOUSE_PASSWORD", "warehouse"),
        dbname=os.getenv("WAREHOUSE_DB", "warehouse"),
    )


def main() -> None:
    """Train from persisted features for a requested point-in-time cutoff."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    repository = PostgresFeatureRepository(_warehouse_connection)
    dataset = load_training_dataset(repository, as_of_date=args.as_of_date)

    # Imported lazily so pure dataset/model tests work without MLflow installed.
    from ml.training.tracking import (  # pylint: disable=import-outside-toplevel
        MLflowRunMetadata,
        start_tracked_run,
    )

    metadata = MLflowRunMetadata(
        as_of_date=dataset.as_of_date.isoformat(),
        dataset_start=dataset.dataset_start.isoformat(),
        dataset_end=dataset.dataset_end.isoformat(),
        feature_view="ml_features.well_monthly_features",
        model_type="linear_regression",
    )
    with start_tracked_run(metadata, run_name=f"train-{dataset.as_of_date}") as run:
        with tempfile.TemporaryDirectory() as directory:
            result = train_dataset(
                dataset,
                run=run,
                artifact_directory=Path(directory),
            )
    print(json.dumps({"run_id": result.run_id, "metrics": result.metrics}))


if __name__ == "__main__":
    main()
