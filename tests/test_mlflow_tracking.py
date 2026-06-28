"""Tests for MLflow experiment tracking helpers."""

from pathlib import Path

import pytest

from ml.training.smoke_tracking import run_smoke_tracking
from ml.training.tracking import MLflowRunMetadata, start_tracked_run


def test_start_tracked_run_sets_tracking_context_and_standard_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configure MLflow and apply standard reproducibility tags."""

    calls: list[tuple[str, object]] = []

    class FakeRun:
        """Minimal context manager matching MLflow's active run shape."""

        def __enter__(self) -> "FakeRun":
            calls.append(("enter", None))
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: object,
        ) -> None:
            calls.append(("exit", exc_type))

    def fake_set_tracking_uri(uri: str) -> None:
        calls.append(("set_tracking_uri", uri))

    def fake_set_experiment(name: str) -> None:
        calls.append(("set_experiment", name))

    def fake_start_run(run_name: str | None = None) -> FakeRun:
        calls.append(("start_run", run_name))
        return FakeRun()

    def fake_set_tags(tags: dict[str, str]) -> None:
        calls.append(("set_tags", tags))

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "file:///tmp/mlruns")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "tracking-tests")
    monkeypatch.setattr(
        "ml.training.tracking.mlflow.set_tracking_uri",
        fake_set_tracking_uri,
    )
    monkeypatch.setattr(
        "ml.training.tracking.mlflow.set_experiment",
        fake_set_experiment,
    )
    monkeypatch.setattr("ml.training.tracking.mlflow.start_run", fake_start_run)
    monkeypatch.setattr("ml.training.tracking.mlflow.set_tags", fake_set_tags)

    metadata = MLflowRunMetadata(
        as_of_date="2026-06-25",
        dataset_start="2026-01-01",
        dataset_end="2026-06-24",
        feature_view="well_daily_features",
        model_type="linear_regression",
        git_sha="abc1234",
    )

    with start_tracked_run(metadata, run_name="smoke"):
        calls.append(("inside", None))

    assert calls == [
        ("set_tracking_uri", "file:///tmp/mlruns"),
        ("set_experiment", "tracking-tests"),
        ("start_run", "smoke"),
        ("enter", None),
        (
            "set_tags",
            {
                "as_of_date": "2026-06-25",
                "dataset_start": "2026-01-01",
                "dataset_end": "2026-06-24",
                "feature_view": "well_daily_features",
                "model_type": "linear_regression",
                "git_sha": "abc1234",
            },
        ),
        ("inside", None),
        ("exit", None),
    ]


def test_start_tracked_run_accepts_temp_file_tracking_uri(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the helper against MLflow's local file-backed store."""

    monkeypatch.setenv("MLFLOW_TRACKING_URI", tmp_path.as_uri())
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "file-store-tests")
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")

    metadata = MLflowRunMetadata(
        as_of_date="2026-06-25",
        dataset_start="2026-01-01",
        dataset_end="2026-06-24",
        feature_view="well_daily_features",
        model_type="dummy_smoke",
    )

    with start_tracked_run(metadata, run_name="file-store-smoke") as run:
        run.log_params({"alpha": 0.1})
        run.log_metrics({"mae": 1.2, "rmse": 1.7})

    assert any(tmp_path.rglob("meta.yaml"))


def test_run_smoke_tracking_records_dummy_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke helper should record only placeholder tracking evidence."""

    events: list[tuple[str, object]] = []

    class FakeTrackedRun:
        """Small stand-in for the tracking context returned by the helper."""

        run_id = "run-123"

        def __enter__(self) -> "FakeTrackedRun":
            events.append(("enter", None))
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: object,
        ) -> None:
            events.append(("exit", exc_type))

        def log_params(self, params: dict[str, object]) -> None:
            """Capture logged smoke parameters."""

            events.append(("params", params))

        def log_metrics(self, metrics: dict[str, float]) -> None:
            """Capture logged smoke metrics."""

            events.append(("metrics", metrics))

    def fake_start_tracked_run(
        metadata: MLflowRunMetadata,
        run_name: str | None = None,
    ) -> FakeTrackedRun:
        events.append(("metadata", metadata))
        events.append(("run_name", run_name))
        return FakeTrackedRun()

    monkeypatch.setattr(
        "ml.training.smoke_tracking.start_tracked_run",
        fake_start_tracked_run,
    )

    run_id = run_smoke_tracking(as_of_date="2026-06-25")

    assert run_id == "run-123"
    assert events == [
        (
            "metadata",
            MLflowRunMetadata(
                as_of_date="2026-06-25",
                dataset_start="2026-06-18",
                dataset_end="2026-06-24",
                feature_view="smoke_tracking_dummy_features",
                model_type="dummy_smoke",
            ),
        ),
        ("run_name", "smoke-tracking"),
        ("enter", None),
        ("params", {"smoke": True, "rows": 7}),
        ("metrics", {"mae": 0.0, "rmse": 0.0}),
        ("exit", None),
    ]
