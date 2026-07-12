"""Dagster schedules for the data platform pipeline."""

from dagster import RunRequest, ScheduleEvaluationContext, SkipReason, schedule

from data_platform.orchestration.assets.bronze import bronze_monthly_partitions
from data_platform.orchestration.jobs import end_to_end_data_job, train_model_job


DATA_PIPELINE_CRON = "0 3 1 * *"
DATA_PIPELINE_TIMEZONE = "America/Argentina/Buenos_Aires"
# Retrain monthly on the 2nd at 04:00 ART, after the data pipeline (1st, 03:00)
# has materialized the latest closed partition of the feature store.
ML_RETRAIN_CRON = "0 4 2 * *"


@schedule(
    job=end_to_end_data_job,
    cron_schedule=DATA_PIPELINE_CRON,
    execution_timezone=DATA_PIPELINE_TIMEZONE,
)
def monthly_data_pipeline_schedule(
    context: ScheduleEvaluationContext,
) -> RunRequest | SkipReason:
    """Launch the latest closed monthly partition for the pipeline run."""
    partition_keys = bronze_monthly_partitions.get_partition_keys(
        current_time=context.scheduled_execution_time,
    )
    if not partition_keys:
        return SkipReason("No closed monthly partition is available yet.")
    return RunRequest(partition_key=partition_keys[-1])


@schedule(
    job=train_model_job,
    cron_schedule=ML_RETRAIN_CRON,
    execution_timezone=DATA_PIPELINE_TIMEZONE,
)
def ml_retraining_schedule(
    context: ScheduleEvaluationContext,
) -> RunRequest | SkipReason:
    """Retrain and promote for the latest closed monthly partition."""
    partition_keys = bronze_monthly_partitions.get_partition_keys(
        current_time=context.scheduled_execution_time,
    )
    if not partition_keys:
        return SkipReason("No closed monthly partition is available yet.")
    return RunRequest(partition_key=partition_keys[-1])
