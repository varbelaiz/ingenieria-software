"""Dagster orchestration entrypoint for the data platform."""

from dagster import Definitions
from dagster_dbt import DbtCliResource

from data_platform.orchestration.assets.bronze import bronze_assets
from data_platform.orchestration.assets.ml import ml_assets
from data_platform.orchestration.assets.transform import dbt_models
from data_platform.orchestration.datahub import build_datahub_sensor
from data_platform.orchestration.dbt_project import dbt_project
from data_platform.orchestration.jobs import end_to_end_data_job, train_model_job
from data_platform.orchestration.schedules import (
    ml_retraining_schedule,
    monthly_data_pipeline_schedule,
)

datahub_sensor = build_datahub_sensor()

defs = Definitions(
    assets=[*bronze_assets, dbt_models, *ml_assets],
    jobs=[end_to_end_data_job, train_model_job],
    schedules=[monthly_data_pipeline_schedule, ml_retraining_schedule],
    sensors=[datahub_sensor] if datahub_sensor is not None else [],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
