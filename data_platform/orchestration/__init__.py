"""Dagster definitions for the data platform."""

from dagster import Definitions

from data_platform.orchestration.assets.bronze import bronze_assets

defs = Definitions(assets=bronze_assets)
