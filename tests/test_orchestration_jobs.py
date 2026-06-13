"""Unit tests for Dagster orchestration jobs."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import subprocess
from typing import Any

import pytest

pytest.importorskip("dagster")

import data_platform.orchestration as orchestration  # noqa: E402
from data_platform.extraction.bronze_loader import BronzeLoad  # noqa: E402
from data_platform.orchestration import jobs  # noqa: E402


@dataclass
class FakeWarehouseConnection:
    """Context manager stub that mirrors the production warehouse connection."""

    events: list[str]

    def __enter__(self) -> "FakeWarehouseConnection":
        self.events.append("connect")
        return self

    def __exit__(self, *args: object) -> None:
        self.events.append("disconnect")


def test_end_to_end_data_job_loads_bronze_before_dbt_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The end-to-end job should load both bronze tables before dbt build."""
    events: list[str] = []
    bronze_loads: list[BronzeLoad] = []

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

    def fake_run_dbt_build() -> subprocess.CompletedProcess[str]:
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
    assert events.index("load:produccion_raw") < events.index("dbt")
    assert events.index("load:pozos_raw") < events.index("dbt")


def test_definitions_register_end_to_end_data_job() -> None:
    """Dagster definitions should expose the operational end-to-end job."""
    assert orchestration.defs.get_job_def("end_to_end_data_job").name == (
        "end_to_end_data_job"
    )
