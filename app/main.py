"""FastAPI application entry point and router registration."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.forecast import router as forecast_router
from app.health import router as health_router
from app.middleware import ApiKeyMiddleware
from app.monitoring import router as monitoring_router, metrics_adapter
from app.predictions import router as predictions_router
from app.wells import router as wells_router
from app.alerts import (
    AlertConfig,
    AlertScheduler,
    LatencyDetector,
    ErrorRateDetector,
    ServiceDownDetector,
    MockNotifier,
    SlackNotifier,
)
from app.alerts.notifiers import Notifier

load_dotenv()
logger = logging.getLogger(__name__)

# Global scheduler instance (will be initialized at startup)
alert_scheduler: AlertScheduler | None = None
scheduler_task: asyncio.Task | None = None


def _create_alert_scheduler() -> AlertScheduler:
    """Create and configure the alert scheduler."""
    config = AlertConfig(
        latency_threshold=float(os.getenv("ALERT_LATENCY_THRESHOLD", "5.0")),
        error_rate_threshold=float(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "0.05")),
        service_down_threshold=int(os.getenv("ALERT_SERVICE_DOWN_THRESHOLD", "30")),
    )

    # Use Slack notifier if webhook URL is provided, otherwise use mock
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    notifier: Notifier
    if webhook_url and webhook_url.strip():
        notifier = SlackNotifier(webhook_url=webhook_url)
        logger.info("Alerts configured to send to Slack")
    else:
        notifier = MockNotifier()
        logger.info("Alerts configured to use MockNotifier (no Slack integration)")

    # Create detectors
    detectors = [
        LatencyDetector(config=config),
        ErrorRateDetector(config=config),
        ServiceDownDetector(config=config),
    ]

    return AlertScheduler(
        config=config,
        notifier=notifier,
        detectors=detectors,
        dedup_window_seconds=int(os.getenv("ALERT_DEDUP_WINDOW_SECONDS", "300")),
    )


async def _run_alert_scheduler(interval_seconds: int = 30) -> None:
    """
    Run alert scheduler periodically.

    Args:
        interval_seconds: How often to check alerts (default 30 seconds)
    """
    logger.info("Alert scheduler started (check interval: %s s)", interval_seconds)
    assert alert_scheduler is not None

    try:
        while True:
            try:
                await alert_scheduler.check_alerts(metrics_adapter)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error during alert check: %s", e, exc_info=True)

            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Alert scheduler cancelled")
        raise


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager for startup and shutdown events.

    Initializes alert scheduler on startup and cancels on shutdown.
    """
    global alert_scheduler, scheduler_task  # pylint: disable=global-statement

    # Startup
    if os.getenv("ALERT_ENABLED", "true").lower() == "true":
        try:
            alert_scheduler = _create_alert_scheduler()
            interval = int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS", "30"))
            scheduler_task = asyncio.create_task(_run_alert_scheduler(interval))
            logger.info("Alert system initialized")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to initialize alert system: %s", e, exc_info=True)
    else:
        logger.info("Alert system disabled")

    yield

    # Shutdown
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            logger.info("Alert scheduler task cancelled")


app = FastAPI(
    title="Plataforma Predictiva de Produccion",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(ApiKeyMiddleware)

app.include_router(wells_router)
app.include_router(forecast_router)
app.include_router(predictions_router)
app.include_router(health_router)
app.include_router(monitoring_router)


def custom_openapi() -> dict:
    """Return OpenAPI schema extended with X-API-Key security scheme."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
