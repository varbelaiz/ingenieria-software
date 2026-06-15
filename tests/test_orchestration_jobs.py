"""Tests for the asset-based orchestration wiring."""

from dagster import AssetKey

from data_platform.orchestration import defs
from data_platform.orchestration.jobs import (
    data_quality_failure_hook,
    end_to_end_data_job,
)


def _all_asset_keys() -> set[str]:
    return {
        key.to_user_string() for key in defs.resolve_asset_graph().get_all_asset_keys()
    }


def test_definitions_expose_bronze_and_dbt_assets() -> None:
    """All bronze and dbt asset keys must be registered in the Definitions."""
    keys = _all_asset_keys()
    assert "bronze_produccion_raw" in keys
    assert "bronze_pozos_raw" in keys
    assert "silver/stg_produccion" in keys
    assert "gold/fct_produccion" in keys


def test_dbt_models_depend_on_bronze_assets() -> None:
    """Silver dbt models must declare bronze assets as upstream parents."""
    graph = defs.resolve_asset_graph()
    parents = graph.get(AssetKey(["silver", "stg_produccion"])).parent_keys
    assert AssetKey(["bronze_produccion_raw"]) in parents


def test_asset_job_has_failure_hook() -> None:
    """The end-to-end asset job must attach the data quality failure hook."""
    assert data_quality_failure_hook in end_to_end_data_job.hooks


def test_schedule_targets_asset_job() -> None:
    """The monthly schedule must target the end_to_end_data_job."""
    schedule = next(
        s for s in defs.schedules if s.name == "monthly_data_pipeline_schedule"
    )
    assert schedule.job_name == "end_to_end_data_job"
    assert schedule.cron_schedule == "0 3 1 * *"
    assert schedule.execution_timezone == "America/Argentina/Buenos_Aires"
