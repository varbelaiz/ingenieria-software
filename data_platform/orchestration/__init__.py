"""Dagster orchestration entrypoint for the data platform."""

from dagster import Definitions

from data_platform.orchestration.assets.bronze import bronze_assets
from data_platform.orchestration.jobs import data_quality_job, end_to_end_data_job
from data_platform.orchestration.schedules import monthly_data_pipeline_schedule

defs = Definitions(
    assets=bronze_assets,
    jobs=[data_quality_job, end_to_end_data_job],
    schedules=[monthly_data_pipeline_schedule],
)
