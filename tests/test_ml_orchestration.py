"""Tests for the ML retraining orchestration wiring and end-to-end compute."""

# pylint: disable=wrong-import-position

from datetime import date
from decimal import Decimal

from pathlib import Path

import pytest

pytest.importorskip("dagster")
pytest.importorskip("dagster_dbt")
pytest.importorskip("mlflow")

from dagster import AssetKey  # noqa: E402

from data_platform.orchestration import defs  # noqa: E402
from data_platform.orchestration.assets import ml as ml_module  # noqa: E402
from data_platform.orchestration.jobs import end_to_end_data_job  # noqa: E402
from ml.features.store import FeatureRow, InMemoryFeatureRepository  # noqa: E402
from ml.registry.client import RegisteredModel  # noqa: E402


FEATURES_KEY = AssetKey(["ml_features", "well_monthly_features"])
TRAINED_KEY = AssetKey(["ml_trained_model"])
PROMOTED_KEY = AssetKey(["ml_promoted_model"])
PARTITION = "2026-06-01"


def _feature_rows() -> list[FeatureRow]:
    """Six monthly snapshots for one well, enough to build a training dataset."""
    rows: list[FeatureRow] = []
    for month in range(1, 7):
        gas = Decimal(str(1000 - (month * 10)))
        rows.append(
            FeatureRow(
                well_id="POZO-001",
                as_of_date=date(2026, month, 1),
                gas_production_current=gas,
                gas_production_avg_3m=gas,
                gas_production_avg_6m=gas,
                gas_production_trend_3m=Decimal("0"),
                oil_production_current=Decimal("10"),
                water_production_current=Decimal("5"),
                producing_days_available=30,
                production_months_available=month,
                formation="Vaca Muerta",
                basin="Neuquina",
                resource_type="Shale",
            )
        )
    return rows


def test_definitions_expose_ml_assets_and_job() -> None:
    """The ML assets and the retraining job must be registered."""
    keys = {
        key.to_user_string() for key in defs.resolve_asset_graph().get_all_asset_keys()
    }
    assert "ml_trained_model" in keys
    assert "ml_promoted_model" in keys
    assert "train_model_job" in {job.name for job in defs.jobs}


def test_trained_model_depends_on_feature_store() -> None:
    """Training must declare the persisted feature model as an upstream dependency."""
    graph = defs.resolve_asset_graph()
    assert FEATURES_KEY in graph.get(TRAINED_KEY).parent_keys


def test_promoted_model_depends_on_trained_model() -> None:
    """Promotion must consume the trained-model run id as its upstream."""
    graph = defs.resolve_asset_graph()
    assert TRAINED_KEY in graph.get(PROMOTED_KEY).parent_keys


def test_retraining_schedule_targets_train_model_job() -> None:
    """The retraining schedule must target the ML job with the documented cron."""
    schedule = next(s for s in defs.schedules if s.name == "ml_retraining_schedule")
    assert schedule.job_name == "train_model_job"
    assert schedule.cron_schedule == "0 4 2 * *"
    assert schedule.execution_timezone == "America/Argentina/Buenos_Aires"


def test_data_job_excludes_ml_assets() -> None:
    """The monthly data pipeline must not retrain the model as a side effect."""
    selected = end_to_end_data_job.selection.resolve(defs.resolve_asset_graph())
    assert TRAINED_KEY not in selected
    assert PROMOTED_KEY not in selected
    assert AssetKey(["bronze_produccion_raw"]) in selected


def test_train_model_job_trains_and_promotes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Materializing the job trains a run and promotes it via the registry."""
    monkeypatch.setattr(
        ml_module,
        "_feature_repository",
        lambda: InMemoryFeatureRepository(_feature_rows()),
    )

    promoted: list[str] = []

    class FakeRegistry:
        """Deterministic registry that always accepts the candidate."""

        def register_run_model(self, run_id: str) -> RegisteredModel:
            """Register the run as candidate with a passing MAE."""
            return RegisteredModel(
                name="well-production-forecast",
                version="1",
                run_id=run_id,
                alias="candidate",
                metrics={"mae": 1.0, "rmse": 1.5},
            )

        def get_champion(self) -> RegisteredModel | None:
            """No champion exists yet."""
            return None

        def set_champion(self, version: str) -> None:
            """Record the promoted version."""
            promoted.append(version)

    monkeypatch.setattr(ml_module, "_registry", FakeRegistry)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", tmp_path.as_uri())
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "orchestration-tests")
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")

    job = defs.resolve_job_def("train_model_job")
    result = job.execute_in_process(partition_key=PARTITION)

    assert result.success
    assert result.output_for_node("ml_trained_model")
    assert result.output_for_node("ml_promoted_model") == "promoted"
    assert promoted == ["1"]
