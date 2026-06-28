"""Tests for deterministic baseline fitting and training-run evidence."""

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from ml.training.dataset import TrainingDataset
from ml.training.train import fit_linear_model, train_dataset


DATASET = TrainingDataset(
    feature_names=("gas_production_current",),
    features=((100.0,), (90.0,), (80.0,)),
    targets=(90.0, 80.0, 70.0),
    dataset_start=date(2024, 1, 1),
    dataset_end=date(2024, 4, 1),
    as_of_date=date(2024, 4, 1),
)


def test_fit_linear_model_and_metrics_are_deterministic() -> None:
    """Identical training data should produce identical model and metrics."""
    first_model, first_metrics = fit_linear_model(DATASET)
    second_model, second_metrics = fit_linear_model(DATASET)

    assert first_model == second_model
    assert first_metrics == second_metrics
    assert first_model.slope == 1.0
    assert first_model.intercept == -10.0
    assert first_metrics == {"mae": 0.0, "rmse": 0.0, "rows": 3.0}


def test_train_dataset_logs_metrics_params_and_model_artifact(
    tmp_path: Path,
) -> None:
    """A training run should leave comparable metrics and a portable artifact."""
    events: list[tuple[str, object]] = []

    class FakeRun:
        run_id = "run-123"

        def log_params(self, params: Mapping[str, str | int | float | bool]) -> None:
            events.append(("params", params))

        def log_metrics(self, metrics: Mapping[str, float]) -> None:
            events.append(("metrics", metrics))

        def log_artifact(
            self, local_path: str | Path, artifact_path: str | None = None
        ) -> None:
            artifact = Path(local_path)
            events.append(("artifact_path", artifact_path))
            events.append(
                ("artifact", json.loads(artifact.read_text(encoding="utf-8")))
            )

    result = train_dataset(DATASET, run=FakeRun(), artifact_directory=tmp_path)

    assert result.run_id == "run-123"
    assert result.metrics["rows"] == 3.0
    assert ("params", {"model_type": "linear_regression", "feature_count": 1}) in events
    assert ("metrics", {"mae": 0.0, "rmse": 0.0, "rows": 3.0}) in events
    assert ("artifact_path", "model") in events
    assert (
        "artifact",
        {
            "feature_names": ["gas_production_current"],
            "intercept": -10.0,
            "model_type": "linear_regression",
            "slope": 1.0,
        },
    ) in events
