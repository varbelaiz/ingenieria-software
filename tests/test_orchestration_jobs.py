"""Unit tests for Dagster orchestration jobs."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
import subprocess
from typing import Any

import pytest

pytest.importorskip("dagster")

from dagster import Backoff, RetryPolicy, build_schedule_context  # noqa: E402

import data_platform.orchestration as orchestration  # noqa: E402
from data_platform.extraction.bronze_loader import BronzeLoad  # noqa: E402
from data_platform.orchestration.assets import bronze  # noqa: E402
from data_platform.orchestration import jobs  # noqa: E402
from data_platform.orchestration.schedules import (  # noqa: E402
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

    def fake_warehouse_connection() -> Iterator[FakeWarehouseConnection]:
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


def test_end_to_end_data_job_rematerializes_the_same_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-running a backfill partition should target the same replaceable period."""
    loaded_rows_by_partition: dict[tuple[str, str], int] = {}
    reprocess_periods: list[str | None] = []

    def fake_warehouse_connection() -> Iterator[FakeWarehouseConnection]:
        return FakeWarehouseConnection([])

    def fake_load_bronze_table(
        conn: FakeWarehouseConnection,
        bronze_load: BronzeLoad,
    ) -> int:
        assert isinstance(conn, FakeWarehouseConnection)
        loaded_rows_by_partition[
            (bronze_load.table_name, bronze_load.load_period)
        ] = len(bronze_load.rows)
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
