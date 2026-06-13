"""Integration and unit tests for persisted dbt quality checks."""

# pylint: disable=wrong-import-position

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

import pytest

psycopg2 = pytest.importorskip("psycopg2")
pytest.importorskip("dagster")

from dagster import build_hook_context  # noqa: E402

from data_platform.ci.seed_bronze import (  # noqa: E402
    LOAD_PERIOD,
    POZOS_FIXTURE,
    PRODUCCION_FIXTURE,
)
from data_platform.extraction.bronze_loader import (  # noqa: E402
    BronzeLoad,
    load_bronze_table,
)
from data_platform.orchestration.dbt import (  # noqa: E402
    DBT_PROFILES_DIR,
    DBT_PROJECT_DIR,
    DbtBuildFailedError,
    build_dbt_build_command,
    run_dbt_build,
)
from data_platform.orchestration.jobs import emit_data_quality_alert  # noqa: E402


def _dbt_available() -> bool:
    return shutil.which("dbt") is not None


def _set_dbt_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DBT_WAREHOUSE_HOST",
        os.getenv("TEST_WAREHOUSE_HOST", os.getenv("WAREHOUSE_HOST", "localhost")),
    )
    monkeypatch.setenv(
        "DBT_WAREHOUSE_PORT",
        os.getenv("TEST_WAREHOUSE_PORT", os.getenv("WAREHOUSE_PORT", "5433")),
    )
    monkeypatch.setenv(
        "DBT_WAREHOUSE_USER",
        os.getenv("TEST_WAREHOUSE_USER", os.getenv("WAREHOUSE_USER", "warehouse")),
    )
    monkeypatch.setenv(
        "DBT_WAREHOUSE_PASSWORD",
        os.getenv(
            "TEST_WAREHOUSE_PASSWORD", os.getenv("WAREHOUSE_PASSWORD", "warehouse")
        ),
    )
    monkeypatch.setenv(
        "DBT_WAREHOUSE_DB",
        os.getenv("TEST_WAREHOUSE_DB", os.getenv("WAREHOUSE_DB", "warehouse")),
    )


def _reset_quality_schemas(warehouse_connection: Any) -> None:
    with warehouse_connection:
        with warehouse_connection.cursor() as cursor:
            cursor.execute(
                """
                DROP SCHEMA IF EXISTS dbt_test_failures CASCADE;
                DROP SCHEMA IF EXISTS gold CASCADE;
                DROP SCHEMA IF EXISTS silver CASCADE;
                DROP SCHEMA IF EXISTS bronze CASCADE;
                """
            )


def _load_invalid_quality_fixture(warehouse_connection: Any) -> None:
    invalid_produccion_rows = [dict(row) for row in PRODUCCION_FIXTURE]
    invalid_produccion_rows[0]["prod_gas"] = "-1.000"

    load_bronze_table(
        warehouse_connection,
        BronzeLoad(
            table_name="produccion_raw",
            load_period=LOAD_PERIOD,
            source_url="https://example.test/produccion-invalid.csv",
            resource_id="ci-produccion-invalid",
            rows=invalid_produccion_rows,
        ),
    )
    load_bronze_table(
        warehouse_connection,
        BronzeLoad(
            table_name="pozos_raw",
            load_period=LOAD_PERIOD,
            source_url="https://example.test/pozos.csv",
            resource_id="ci-pozos",
            rows=POZOS_FIXTURE,
        ),
    )


def test_dbt_build_persists_failure_rows_for_invalid_gold_data(
    warehouse_connection: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing dbt build should persist invalid rows into dbt_test_failures."""
    if not _dbt_available():
        pytest.skip("dbt is not installed")

    _set_dbt_env(monkeypatch)
    _reset_quality_schemas(warehouse_connection)
    _load_invalid_quality_fixture(warehouse_connection)

    command = build_dbt_build_command()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0

    with warehouse_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'dbt_test_failures'
            ORDER BY table_name
            """
        )
        failure_tables = [row[0] for row in cursor.fetchall()]

    assert failure_tables

    with warehouse_connection.cursor() as cursor:
        persisted_failure_rows = 0
        for table_name in failure_tables:
            cursor.execute(
                psycopg2.sql.SQL("SELECT count(*) FROM {}.{}").format(
                    psycopg2.sql.Identifier("dbt_test_failures"),
                    psycopg2.sql.Identifier(table_name),
                )
            )
            persisted_failure_rows += int(cursor.fetchone()[0])

    assert persisted_failure_rows > 0


def test_build_dbt_build_command_uses_expected_directories() -> None:
    """The dbt orchestration helper should build the canonical command."""
    command = build_dbt_build_command()

    assert command[1:4] == ["build", "--select", "silver gold"]
    assert command[4:] == [
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROFILES_DIR),
    ]


def test_run_dbt_build_raises_on_non_zero_exit_code() -> None:
    """The helper should raise when dbt exits with a failing quality gate."""

    def failing_runner(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["dbt", "build"],
            returncode=2,
            stdout="",
            stderr="quality test failed",
        )

    with pytest.raises(DbtBuildFailedError, match="exit code 2"):
        run_dbt_build(["dbt", "build"], runner=failing_runner)


def test_emit_data_quality_alert_logs_structured_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Structured alerts should be logged even without a webhook configured."""
    with build_hook_context() as context:
        payload = emit_data_quality_alert(
            context,
            error_message="dbt build failed",
            webhook_url=None,
        )
    captured = capsys.readouterr()

    assert payload["event"] == "data_quality_job_failed"
    assert payload["error"] == "dbt build failed"
    assert "data_quality_alert=" in captured.err
