"""Dagster orchestration entrypoint for the data platform."""

from dagster import Definitions

from data_platform.orchestration.assets.bronze import bronze_assets
from data_platform.orchestration.jobs import data_quality_job

defs = Definitions(assets=bronze_assets, jobs=[data_quality_job])
