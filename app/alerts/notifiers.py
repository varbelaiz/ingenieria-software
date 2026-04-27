"""Alert notifiers for sending alerts to various channels."""

from abc import ABC, abstractmethod
from typing import Optional
import httpx
from app.alerts.models import AlertEvent


class Notifier(ABC):
    """Abstract base class for alert notifiers."""

    @abstractmethod
    async def send(self, alert: AlertEvent) -> bool:
        """
        Send an alert notification.

        Args:
            alert: The alert event to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass


class MockNotifier(Notifier):
    """Mock notifier that stores alerts in memory for testing."""

    def __init__(self) -> None:
        """Initialize MockNotifier with empty alerts list."""
        self.alerts: list[AlertEvent] = []

    async def send(self, alert: AlertEvent) -> bool:
        """
        Store alert in memory.

        Args:
            alert: The alert event to store

        Returns:
            Always True
        """
        self.alerts.append(alert)
        return True

    def get_alerts(self) -> list[AlertEvent]:
        """Get all stored alerts."""
        return self.alerts.copy()

    def clear(self) -> None:
        """Clear all stored alerts."""
        self.alerts.clear()


class SlackNotifier(Notifier):
    """Notifier that sends alerts to Slack via webhook."""

    def __init__(self, webhook_url: str) -> None:
        """
        Initialize SlackNotifier with webhook URL.

        Args:
            webhook_url: Slack incoming webhook URL
        """
        self.webhook_url = webhook_url

    async def send(self, alert: AlertEvent) -> bool:
        """
        Send alert to Slack.

        Args:
            alert: The alert event to send

        Returns:
            True if sent successfully, False otherwise
        """
        payload = self._format_slack_message(alert)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _format_slack_message(alert: AlertEvent) -> dict:
        """
        Format alert as Slack message payload.

        Args:
            alert: The alert event

        Returns:
            Dictionary formatted for Slack webhook
        """
        severity_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🔴",
            "critical": "🔴❗",
        }

        emoji = severity_emoji.get(alert.severity.name.lower(), "⚠️")
        alert_type_name = alert.alert_type.value.replace("_", " ").title()

        message_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Alert: {alert_type_name}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Status:* {alert.status.value}\n*Message:* {alert.message}",
                },
            },
        ]

        if alert.context:
            context_text = "\n".join(
                [f"• *{k}:* {v}" for k, v in alert.context.items()]
            )
            message_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Context:*\n{context_text}",
                    },
                }
            )

        return {
            "text": f"Alert: {alert_type_name} - {alert.message}",
            "blocks": message_blocks,
        }
