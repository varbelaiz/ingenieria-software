"""Dagster assets that retrain and promote the Phase 3 production model.

These assets orchestrate the ML flow already implemented under ``ml/``: they read
point-in-time features from the persisted feature store, train a reproducible model
for the partition's ``as_of_date``, log the run to MLflow, and evaluate the candidate
for champion promotion. Both assets are partitioned by month, so retraining "for a
given day" is materializing the corresponding monthly partition.
"""

from datetime import date
import os
from pathlib import Path
import tempfile
from typing import Any

from dagster import AssetExecutionContext, AssetIn, Output, asset
from dagster_dbt import get_asset_key_for_model

from data_platform.orchestration.assets.bronze import bronze_monthly_partitions
from data_platform.orchestration.assets.transform import dbt_models

WELL_FEATURES_MODEL = "well_monthly_features"
PROMOTION_MAX_MAE_ENV = "ML_PROMOTION_MAX_MAE"
DEFAULT_PROMOTION_MAX_MAE = 100.0

_FEATURES_ASSET_KEY = get_asset_key_for_model([dbt_models], WELL_FEATURES_MODEL)


def _warehouse_connection() -> Any:
    """Open a warehouse connection using the same env vars as the bronze assets."""

    # Imported lazily so environments without the data group can still import
    # this module for definition validation.
    import psycopg2  # pylint: disable=import-outside-toplevel,import-error

    return psycopg2.connect(
        host=os.getenv("WAREHOUSE_HOST", "localhost"),
        port=int(os.getenv("WAREHOUSE_PORT", "5433")),
        user=os.getenv("WAREHOUSE_USER", "warehouse"),
        password=os.getenv("WAREHOUSE_PASSWORD", "warehouse"),
        dbname=os.getenv("WAREHOUSE_DB", "warehouse"),
    )


def _feature_repository() -> Any:
    """Build the persisted feature repository (indirection eases test injection)."""

    from ml.features.store import (  # pylint: disable=import-outside-toplevel
        PostgresFeatureRepository,
    )

    return PostgresFeatureRepository(_warehouse_connection)


def _registry() -> Any:
    """Build the MLflow-backed registry client (indirection eases test injection)."""

    from ml.registry.client import (  # pylint: disable=import-outside-toplevel
        MLflowRegistryClient,
    )

    return MLflowRegistryClient()


def _promotion_max_mae() -> float:
    """Resolve the maximum accepted MAE for champion promotion."""

    return float(os.getenv(PROMOTION_MAX_MAE_ENV, str(DEFAULT_PROMOTION_MAX_MAE)))


@asset(
    partitions_def=bronze_monthly_partitions,
    group_name="ml",
    deps=[_FEATURES_ASSET_KEY],
    compute_kind="mlflow",
)
def ml_trained_model(context: AssetExecutionContext) -> Output[str]:
    """Train a model for the partition's ``as_of_date`` and log it to MLflow."""

    from ml.training.dataset import (  # pylint: disable=import-outside-toplevel
        load_training_dataset,
    )
    from ml.training.tracking import (  # pylint: disable=import-outside-toplevel
        MLflowRunMetadata,
        start_tracked_run,
    )
    from ml.training.train import (  # pylint: disable=import-outside-toplevel
        train_dataset,
    )

    as_of_date = date.fromisoformat(context.partition_key)
    dataset = load_training_dataset(_feature_repository(), as_of_date=as_of_date)

    metadata = MLflowRunMetadata(
        as_of_date=dataset.as_of_date.isoformat(),
        dataset_start=dataset.dataset_start.isoformat(),
        dataset_end=dataset.dataset_end.isoformat(),
        feature_view=f"ml_features.{WELL_FEATURES_MODEL}",
        model_type="linear_regression",
    )
    with start_tracked_run(metadata, run_name=f"train-{dataset.as_of_date}") as run:
        with tempfile.TemporaryDirectory() as directory:
            result = train_dataset(
                dataset,
                run=run,
                artifact_directory=Path(directory),
            )

    run_id = result.run_id or ""
    context.log.info("Trained run_id=%s metrics=%s", run_id, result.metrics)
    return Output(
        run_id,
        metadata={
            "run_id": run_id,
            "mae": result.metrics["mae"],
            "rmse": result.metrics["rmse"],
            "rows": result.metrics["rows"],
        },
    )


@asset(
    partitions_def=bronze_monthly_partitions,
    group_name="ml",
    ins={"run_id": AssetIn("ml_trained_model")},
    compute_kind="mlflow",
)
def ml_promoted_model(context: AssetExecutionContext, run_id: str) -> Output[str]:
    """Register the trained run and promote it to champion when it passes policy."""

    from ml.registry.promote import (  # pylint: disable=import-outside-toplevel
        register_and_promote,
    )

    if not run_id:
        raise ValueError("Upstream training produced no run_id to promote.")

    decision = register_and_promote(
        _registry(),
        run_id=run_id,
        max_mae=_promotion_max_mae(),
    )
    context.log.info(
        "Promotion decision status=%s version=%s reason=%s",
        decision.status,
        decision.version,
        decision.reason,
    )
    return Output(
        decision.status,
        metadata={
            "status": decision.status,
            "version": decision.version,
            "reason": decision.reason,
        },
    )


ml_assets = [ml_trained_model, ml_promoted_model]
