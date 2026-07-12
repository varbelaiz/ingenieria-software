"""Smoke command for verifying MLflow experiment tracking locally."""

from __future__ import annotations

from datetime import date, timedelta

from ml.training.tracking import MLflowRunMetadata, start_tracked_run


def run_smoke_tracking(as_of_date: str | None = None) -> str | None:
    """Record a dummy MLflow run to validate tracking configuration."""

    run_date = date.fromisoformat(as_of_date) if as_of_date else date.today()
    dataset_end = run_date - timedelta(days=1)
    dataset_start = run_date - timedelta(days=7)

    metadata = MLflowRunMetadata(
        as_of_date=run_date.isoformat(),
        dataset_start=dataset_start.isoformat(),
        dataset_end=dataset_end.isoformat(),
        feature_view="smoke_tracking_dummy_features",
        model_type="dummy_smoke",
    )

    with start_tracked_run(metadata, run_name="smoke-tracking") as run:
        run.log_params({"smoke": True, "rows": 7})
        run.log_metrics({"mae": 0.0, "rmse": 0.0})
        return run.run_id


def main() -> None:
    """CLI entrypoint for `python -m ml.training.smoke_tracking`."""

    run_id = run_smoke_tracking()
    print(f"MLflow smoke run recorded: {run_id or 'unknown run id'}")


if __name__ == "__main__":
    main()
