"""Dagster jobs for operational data quality gates."""

import json
import os
from urllib import error, request

from dagster import (
    HookContext,
    In,
    Nothing,
    OpExecutionContext,
    failure_hook,
    job,
    op,
)
from dagster._core.errors import DagsterInvalidPropertyError

from data_platform.orchestration.dbt import run_dbt_build, run_dbt_source_freshness


ALERT_WEBHOOK_ENV = "DATA_QUALITY_ALERT_WEBHOOK_URL"


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
        op_def = context.op
    except (AttributeError, DagsterInvalidPropertyError):
        op_def = None
    if op_def is not None:
        op_name = op_def.name
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


def _send_data_quality_webhook(
    context: HookContext | OpExecutionContext,
    payload: dict[str, str],
    webhook_url: str,
) -> None:
    """Send the alert payload to a webhook at Dagster job runtime."""
    if not webhook_url.startswith("https://"):
        raise ValueError(
            f"Webhook URL must start with 'https://'; got: {webhook_url!r}"
        )
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
def run_dbt_quality_source_freshness(context: OpExecutionContext) -> None:
    """Check source freshness so stale data blocks downstream promotion."""
    completed = run_dbt_source_freshness()
    if completed.stdout:
        context.log.info(completed.stdout)
    if completed.stderr:
        context.log.info(completed.stderr)


@op(ins={"_freshness": In(Nothing)})
def run_dbt_quality_build(context: OpExecutionContext) -> None:
    """Execute dbt build so failing tests block downstream promotion."""
    completed = run_dbt_build()
    if completed.stdout:
        context.log.info(completed.stdout)
    if completed.stderr:
        context.log.info(completed.stderr)


@job(hooks={data_quality_failure_hook})
def data_quality_job() -> None:
    """Minimal Dagster job that enforces silver/gold data quality."""
    # Dagster injects the op context at runtime.
    # pylint: disable=no-value-for-parameter
    run_dbt_quality_build(run_dbt_quality_source_freshness())
