"""Alert deduplication logic to prevent spam."""

import threading
import time
from app.alerts.models import AlertEvent


class AlertDeduplicator:
    """Deduplicates alerts to prevent spam within a configured window."""

    def __init__(self, dedup_window_seconds: int = 300) -> None:
        """
        Initialize AlertDeduplicator.

        Args:
            dedup_window_seconds: Time window in seconds for deduplication
        (default 5 min)
        """
        self.dedup_window_seconds = dedup_window_seconds
        self._alert_cache: dict[str, float] = {}
        self._lock = threading.Lock()

    def should_notify(self, alert: AlertEvent) -> bool:
        """
        Determine if alert should be notified.

        An alert is notified if:
        - It hasn't been seen before, OR
        - The dedup window has expired since last notification

        Args:
            alert: The alert event

        Returns:
            True if alert should be notified, False if deduplicated
        """
        key = alert.unique_key()
        current_time = time.time()

        with self._lock:
            # Check if alert is in cache and window hasn't expired
            if key in self._alert_cache:
                last_seen = self._alert_cache[key]
                age = current_time - last_seen

                if age < self.dedup_window_seconds:
                    # Still within dedup window - don't notify
                    return False

            # Either new alert or window expired - notify and update cache
            self._alert_cache[key] = current_time
            return True

    def cleanup(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()

        with self._lock:
            expired_keys = [
                key
                for key, timestamp in self._alert_cache.items()
                if (current_time - timestamp) >= self.dedup_window_seconds
            ]

            for key in expired_keys:
                del self._alert_cache[key]
