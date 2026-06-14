"""Optional DataHub sensor integration for Dagster metadata emission."""

from __future__ import annotations

from os import getenv
from typing import Any, cast

from dagster import SensorDefinition


DATAHUB_SENSOR_NAME = "datahub_sensor"
DEFAULT_DATAHUB_GMS_URL = "http://localhost:8080"
DEFAULT_DAGSTER_URL = "http://localhost:3001"


def build_datahub_sensor() -> SensorDefinition | None:
    """Build the DataHub sensor when the optional plugin is installed."""
    try:
        from datahub.ingestion.graph.client import DatahubClientConfig
        from datahub_dagster_plugin.sensors.datahub_sensors import (
            DatahubDagsterSourceConfig,
            make_datahub_sensor,
        )
    except ImportError:
        return None

    config = DatahubDagsterSourceConfig(
        datahub_client_config=DatahubClientConfig(
            server=getenv("DATAHUB_GMS_URL", DEFAULT_DATAHUB_GMS_URL),
            token=getenv("DATAHUB_GMS_TOKEN"),
        ),
        dagster_url=getenv("DAGSTER_URL", DEFAULT_DAGSTER_URL),
        capture_asset_materialization=True,
        capture_input_output=True,
    )
    sensor: Any = make_datahub_sensor(config=config)
    return cast(SensorDefinition, sensor)
