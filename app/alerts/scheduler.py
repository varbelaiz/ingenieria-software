"""Alert scheduler for periodic checking and notification."""

import logging

from app.alerts.models import AlertConfig, AlertEvent
from app.alerts.notifiers import Notifier
from app.alerts.detectors import AlertDetector, MetricsProvider
from app.alerts.deduplicator import AlertDeduplicator

logger = logging.getLogger(__name__)


class AlertScheduler:
    """Orchestrates alert detection, deduplication, and notification."""

    def __init__(
        self,
        config: AlertConfig,
        notifier: Notifier,
        detectors: list[AlertDetector],
        dedup_window_seconds: int = 300,
    ) -> None:
        """
        Initialize AlertScheduler.

        Args:
            config: Alert configuration with thresholds
            notifier: Notifier instance for sending alerts
            detectors: List of alert detectors to run
            dedup_window_seconds: Deduplication window (default 5 min)
        """
        self.config = config
        self.notifier = notifier
        self.detectors = detectors
        self.deduplicator = AlertDeduplicator(dedup_window_seconds=dedup_window_seconds)

    async def check_alerts(self, metrics: MetricsProvider) -> None:
        """
        Check all detectors and send alerts.

        This method:
        1. Runs all detectors against metrics
        2. Deduplicates alerts
        3. Sends notifications for new/re-triggered alerts

        Args:
            metrics: The metrics provider
        """
        for detector in self.detectors:
            try:
                alert = detector.detect(metrics)

                if alert is None:
                    continue

                # Check if alert should be notified (deduplication)
                if not self.deduplicator.should_notify(alert):
                    logger.debug("Alert deduplicated: %s", alert.alert_type.value)
                    continue

                # Send notification
                await self._send_alert(alert)

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Error in detector %s: %s",
                    detector.__class__.__name__,
                    e,
                    exc_info=True,
                )
                continue

        # Periodic cleanup of expired dedup entries
        self.deduplicator.cleanup()

    async def _send_alert(self, alert: AlertEvent) -> None:
        """
        Send alert notification.

        Args:
            alert: The alert event to send
        """
        try:
            success = await self.notifier.send(alert)

            if success:
                logger.info(
                    "Alert sent: %s - %s", alert.alert_type.value, alert.message
                )
            else:
                logger.warning("Alert notification failed: %s", alert.alert_type.value)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Exception while sending alert: %s", e, exc_info=True)
