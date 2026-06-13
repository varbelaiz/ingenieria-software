"""Dagster jobs for operational data quality gates."""

import json
import os
from typing import Any
from urllib import error, request

from dagster import (
    HookContext,
    OpExecutionContext,
    failure_hook,
    job,
    op,
)
from dagster._core.errors import DagsterInvalidPropertyError

from data_platform.extraction.bronze_loader import BronzeLoad, load_bronze_table
from data_platform.extraction.pozos import (
    POZOS_DEFAULT_URL,
    POZOS_RESOURCE_ID,
    POZOS_URL_ENV,
    fetch_pozos_rows,
)
from data_platform.extraction.produccion import (
    PRODUCCION_DEFAULT_URL,
    PRODUCCION_RESOURCE_ID,
    PRODUCCION_URL_ENV,
    fetch_produccion_rows,
)
from data_platform.orchestration.assets.bronze import (
    bronze_monthly_partitions,
    warehouse_connection,
)
from data_platform.orchestration.dbt import run_dbt_build


ALERT_WEBHOOK_ENV = "DATA_QUALITY_ALERT_WEBHOOK_URL"


def _partition_key(context: OpExecutionContext) -> str:
    """Read the active Dagster partition key for bronze load metadata."""
    return context.partition_key


def _safe_context_value(
    context: HookContext | OpExecutionContext,
    attribute: str,
    default: str,
) -> str:
    """Read context attributes defensively for Dagster runtime and tests."""
    try:
        value = getattr(context, attribute)
    except (AttributeError, DagsterInvalidPropertyError):
        return default
    return default if value is None else str(value)


def emit_data_quality_alert(
    context: HookContext | OpExecutionContext,
    *,
    error_message: str,
    webhook_url: str | None = None,
) -> dict[str, str]:
    """Log a structured alert and optionally forward it to a webhook."""
    op_name = "unknown"
    try:
        op = context.op
    except (AttributeError, DagsterInvalidPropertyError):
        op = None
    if op is not None:
        op_name = op.name
    payload = {
        "event": "data_quality_job_failed",
        "job_name": _safe_context_value(context, "job_name", "data_quality_job"),
        "op_name": op_name,
        "run_id": _safe_context_value(context, "run_id", "unknown"),
        "error": error_message,
    }
    context.log.error("data_quality_alert=%s", json.dumps(payload, sort_keys=True))
    if webhook_url:
        _send_data_quality_webhook(context, payload, webhook_url)
    return payload


def _log_completed_dbt_build(
    context: OpExecutionContext,
    completed: Any,
) -> None:
    """Forward dbt process output to Dagster logs."""
    if completed.stdout:
        context.log.info(completed.stdout)
    if completed.stderr:
        context.log.info(completed.stderr)


def _send_data_quality_webhook(
    context: HookContext | OpExecutionContext,
    payload: dict[str, str],
    webhook_url: str,
) -> None:
    """Send the alert payload to an optional webhook without blocking the PR."""
    webhook_request = request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(webhook_request, timeout=5):
            context.log.info("Forwarded data quality alert to configured webhook.")
    except error.URLError as exc:
        context.log.warning("Failed to deliver data quality webhook alert: %s", exc)


@failure_hook
def data_quality_failure_hook(context: HookContext) -> None:
    """Emit a structured alert when the dbt quality gate fails."""
    error_message = (
        str(context.op_exception) if context.op_exception else "Unknown failure"
    )
    emit_data_quality_alert(
        context,
        error_message=error_message,
        webhook_url=os.getenv(ALERT_WEBHOOK_ENV),
    )


@op
def run_dbt_quality_build(context: OpExecutionContext) -> None:
    """Execute dbt build so failing tests block downstream promotion."""
    completed = run_dbt_build()
    _log_completed_dbt_build(context, completed)


@job(hooks={data_quality_failure_hook})
def data_quality_job() -> None:
    """Minimal Dagster job that enforces silver/gold data quality."""
    # Dagster injects the op context at runtime.
    # pylint: disable=no-value-for-parameter
    run_dbt_quality_build()


@op
def load_bronze_produccion_raw(context: OpExecutionContext) -> int:
    """Load raw production data into bronze before downstream dbt models run."""
    rows = fetch_produccion_rows()
    with warehouse_connection() as conn:
        row_count = load_bronze_table(
            conn,
            BronzeLoad(
                table_name="produccion_raw",
                load_period=_partition_key(context),
                source_url=os.getenv(PRODUCCION_URL_ENV, PRODUCCION_DEFAULT_URL),
                resource_id=PRODUCCION_RESOURCE_ID,
                rows=rows,
            ),
        )
    context.log.info("Loaded %s rows into bronze.produccion_raw", row_count)
    return row_count


@op
def load_bronze_pozos_raw(
    context: OpExecutionContext,
    produccion_row_count: int,
) -> int:
    """Load raw wells data into bronze before downstream dbt models run."""
    context.log.info(
        "Starting bronze.pozos_raw load after bronze.produccion_raw rows=%s",
        produccion_row_count,
    )
    rows = fetch_pozos_rows()
    with warehouse_connection() as conn:
        row_count = load_bronze_table(
            conn,
            BronzeLoad(
                table_name="pozos_raw",
                load_period=_partition_key(context),
                source_url=os.getenv(POZOS_URL_ENV, POZOS_DEFAULT_URL),
                resource_id=POZOS_RESOURCE_ID,
                rows=rows,
            ),
        )
    context.log.info("Loaded %s rows into bronze.pozos_raw", row_count)
    return row_count


@op
def run_end_to_end_dbt_build(
    context: OpExecutionContext,
    produccion_row_count: int,
    pozos_row_count: int,
) -> None:
    """Build silver/gold after both bronze sources have landed."""
    context.log.info(
        "Starting dbt build after bronze loads: produccion=%s, pozos=%s",
        produccion_row_count,
        pozos_row_count,
    )
    completed = run_dbt_build()
    _log_completed_dbt_build(context, completed)


@job(partitions_def=bronze_monthly_partitions, hooks={data_quality_failure_hook})
def end_to_end_data_job() -> None:
    """Load bronze sources and then run dbt build for silver/gold/tests."""
    produccion_row_count = load_bronze_produccion_raw()
    run_end_to_end_dbt_build(
        produccion_row_count,
        load_bronze_pozos_raw(produccion_row_count),
    )
