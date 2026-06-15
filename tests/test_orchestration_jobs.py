"""Unit tests for Dagster orchestration jobs."""

# flake8: noqa: E402
# pylint: disable=wrong-import-position

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import subprocess

import pytest

pytest.importorskip("dagster")

from dagster import Backoff, RunRequest, RetryPolicy, build_schedule_context

from data_platform import orchestration
from data_platform.extraction.bronze_loader import BronzeLoad
from data_platform.orchestration.assets import bronze
from data_platform.orchestration import jobs
from data_platform.orchestration.schedules import (
    monthly_data_pipeline_schedule,
)


@dataclass
class FakeWarehouseConnection:
    """Context manager stub that mirrors the production warehouse connection."""

    events: list[str]

    def __enter__(self) -> "FakeWarehouseConnection":
        self.events.append("connect")
        return self

    def __exit__(self, *args: object) -> None:
        self.events.append("disconnect")


def assert_exponential_backoff_retry_policy(
    retry_policy: RetryPolicy | None,
) -> None:
    """Assert the Dagster retry policy matches the orchestration standard."""
    assert retry_policy is not None
    assert retry_policy.max_retries == 3
    assert retry_policy.delay == 30
    assert retry_policy.backoff == Backoff.EXPONENTIAL


def test_bronze_assets_define_exponential_backoff_retry_policy() -> None:
    """Bronze assets should retry transient extraction/load failures."""
    assert_exponential_backoff_retry_policy(
        bronze.bronze_produccion_raw.op.retry_policy,
    )
    assert_exponential_backoff_retry_policy(
        bronze.bronze_pozos_raw.op.retry_policy,
    )


def test_orchestration_ops_define_exponential_backoff_retry_policy() -> None:
    """Operational steps should retry transient extraction/dbt failures."""
    assert_exponential_backoff_retry_policy(jobs.run_dbt_quality_build.retry_policy)
    assert_exponential_backoff_retry_policy(
        jobs.load_bronze_produccion_raw.retry_policy,
    )
    assert_exponential_backoff_retry_policy(jobs.load_bronze_pozos_raw.retry_policy)
    assert_exponential_backoff_retry_policy(jobs.run_end_to_end_dbt_build.retry_policy)


def test_end_to_end_data_job_loads_bronze_before_dbt_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The end-to-end job should load both bronze tables before dbt build."""
    events: list[str] = []
    bronze_loads: list[BronzeLoad] = []
    reprocess_periods: list[str | None] = []

    def fake_warehouse_connection() -> FakeWarehouseConnection:
        return FakeWarehouseConnection(events)

    def fake_load_bronze_table(
        conn: FakeWarehouseConnection,
        bronze_load: BronzeLoad,
    ) -> int:
        assert isinstance(conn, FakeWarehouseConnection)
        bronze_loads.append(bronze_load)
        events.append(f"load:{bronze_load.table_name}")
        return len(bronze_load.rows)

    def fake_run_dbt_build(
        *,
        reprocess_period: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        reprocess_periods.append(reprocess_period)
        events.append("dbt")
        return subprocess.CompletedProcess(
            args=["dbt", "build"],
            returncode=0,
            stdout="dbt ok",
            stderr="",
        )

    monkeypatch.setattr(jobs, "fetch_produccion_rows", lambda: [{"idpozo": "1"}])
    monkeypatch.setattr(jobs, "fetch_pozos_rows", lambda: [{"idpozo": "1"}])
    monkeypatch.setattr(jobs, "warehouse_connection", fake_warehouse_connection)
    monkeypatch.setattr(jobs, "load_bronze_table", fake_load_bronze_table)
    monkeypatch.setattr(jobs, "run_dbt_build", fake_run_dbt_build)

    result = jobs.end_to_end_data_job.execute_in_process(partition_key="2026-01-01")

    assert result.success
    assert [load.table_name for load in bronze_loads] == [
        "produccion_raw",
        "pozos_raw",
    ]
    assert [load.load_period for load in bronze_loads] == [
        "2026-01-01",
        "2026-01-01",
    ]
    assert reprocess_periods == ["2026-01-01"]
    assert events.index("load:produccion_raw") < events.index("dbt")
    assert events.index("load:pozos_raw") < events.index("dbt")


def test_end_to_end_data_job_passes_partition_key_to_ops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every op in the job should receive the active partition key."""
    loaded_rows_by_partition: dict[tuple[str, str], int] = {}
    reprocess_periods: list[str | None] = []

    def fake_warehouse_connection() -> FakeWarehouseConnection:
        return FakeWarehouseConnection([])

    def fake_load_bronze_table(
        conn: FakeWarehouseConnection,
        bronze_load: BronzeLoad,
    ) -> int:
        assert isinstance(conn, FakeWarehouseConnection)
        loaded_rows_by_partition[(bronze_load.table_name, bronze_load.load_period)] = (
            len(bronze_load.rows)
        )
        return len(bronze_load.rows)

    def fake_run_dbt_build(
        *,
        reprocess_period: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        reprocess_periods.append(reprocess_period)
        return subprocess.CompletedProcess(
            args=["dbt", "build"],
            returncode=0,
            stdout="dbt ok",
            stderr="",
        )

    monkeypatch.setattr(jobs, "fetch_produccion_rows", lambda: [{"idpozo": "1"}])
    monkeypatch.setattr(jobs, "fetch_pozos_rows", lambda: [{"idpozo": "1"}])
    monkeypatch.setattr(jobs, "warehouse_connection", fake_warehouse_connection)
    monkeypatch.setattr(jobs, "load_bronze_table", fake_load_bronze_table)
    monkeypatch.setattr(jobs, "run_dbt_build", fake_run_dbt_build)

    first_result = jobs.end_to_end_data_job.execute_in_process(
        partition_key="2026-01-01",
    )
    second_result = jobs.end_to_end_data_job.execute_in_process(
        partition_key="2026-01-01",
    )

    assert first_result.success
    assert second_result.success
    assert loaded_rows_by_partition == {
        ("produccion_raw", "2026-01-01"): 1,
        ("pozos_raw", "2026-01-01"): 1,
    }
    assert reprocess_periods == ["2026-01-01", "2026-01-01"]


def test_end_to_end_data_job_uses_bronze_monthly_partitions() -> None:
    """Backfills should use the same monthly partitions as the bronze assets."""
    assert jobs.end_to_end_data_job.partitions_def is bronze.bronze_monthly_partitions


def test_definitions_register_end_to_end_data_job() -> None:
    """Dagster definitions should expose the operational end-to-end job."""
    assert orchestration.defs.get_job_def("end_to_end_data_job").name == (
        "end_to_end_data_job"
    )


def test_definitions_register_monthly_data_pipeline_schedule() -> None:
    """Dagster definitions should expose the monthly pipeline schedule."""
    schedule = orchestration.defs.get_schedule_def("monthly_data_pipeline_schedule")

    assert schedule.name == "monthly_data_pipeline_schedule"
    assert schedule.job_name == "end_to_end_data_job"
    assert schedule.cron_schedule == "0 3 1 * *"
    assert schedule.execution_timezone == "America/Argentina/Buenos_Aires"


def test_definitions_expose_optional_datahub_sensor_hook() -> None:
    """Governance metadata should have a real Dagster sensor integration point."""
    assert hasattr(orchestration, "datahub_sensor")

    if orchestration.datahub_sensor is None:
        assert not orchestration.defs.get_repository_def().has_sensor_def(
            "datahub_sensor",
        )
    else:
        assert orchestration.datahub_sensor.name == "datahub_sensor"
        assert (
            orchestration.defs.get_sensor_def("datahub_sensor")
            is orchestration.datahub_sensor
        )


def test_monthly_data_pipeline_schedule_requests_monthly_partition() -> None:
    """The monthly schedule should launch the latest closed monthly partition."""
    repository_def = orchestration.defs.get_repository_def()
    context = build_schedule_context(
        scheduled_execution_time=datetime(2026, 6, 1, 3, 0),
        repository_def=repository_def,
    )

    schedule = repository_def.get_schedule_def("monthly_data_pipeline_schedule")
    run_requests = schedule.evaluate_tick(context).run_requests

    assert len(run_requests) == 1
    assert run_requests[0].partition_key == "2026-05-01"


def test_monthly_data_pipeline_schedule_function_returns_latest_partition() -> None:
    """The schedule function should request the latest closed monthly partition."""
    context = build_schedule_context(
        scheduled_execution_time=datetime(2026, 6, 1, 3, 0),
    )

    run_request = monthly_data_pipeline_schedule(context)

    assert isinstance(run_request, RunRequest)
    assert run_request.partition_key == "2026-05-01"
