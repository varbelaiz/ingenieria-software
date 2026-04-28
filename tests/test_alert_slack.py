"""Test that alerts are properly sent to Slack."""


import asyncio
import time
from typing import Optional
import os
import sys
import httpx

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.alerts import (
    AlertConfig,
    AlertScheduler,
    SlackNotifier,
    LatencyDetector,
    ErrorRateDetector,
    ServiceDownDetector,
)
from app.alerts.detectors import MetricsProvider

# antes de arrancar hacer cd ..  


class PrometheusMetricsProvider(MetricsProvider):
    """Read metrics from Prometheus."""

    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        self.prometheus_url = prometheus_url
        self.client = httpx.Client()

    def _query(self, promql: str) -> Optional[float]:
        """Execute a PromQL query and return scalar result."""
        try:
            response = self.client.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": promql},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                return None

            result = data.get("data", {}).get("result", [])
            if not result:
                return None

            return float(result[0]["value"][1])
        except Exception as e:
            print(f"⚠️  Error querying Prometheus: {e}")
            return None

    def get_average_latency(self) -> Optional[float]:
        """Get average request latency in seconds (last 5 minutes)."""
        query = (
            "rate(forecast_api_request_duration_seconds_sum"
            "[5m]) / rate(forecast_api_request_duration_seconds_count[5m])"
        )
        return self._query(query)

    def get_error_rate(self) -> Optional[float]:
        """Get error rate as decimal (0-1) in last 5 minutes."""
        query = (
            "rate(forecast_api_errors_total[5m]) / "
            "(rate(forecast_api_requests_total[5m]) + 0.0001)"
        )
        latency = self._query(query)
        return latency if latency and latency <= 1.0 else None

    def get_request_count_last_seconds(self, seconds: int = 30) -> int:
        """Get number of requests in the last N seconds."""
        duration = f"{seconds}s"
        query = f"rate(forecast_api_requests_total[{duration}]) * {seconds}"
        result = self._query(query)
        return int(result) if result else 0


async def generate_traffic_with_errors(
    api_url: str = "http://localhost:8000",
    duration: int = 30,
):
    """Generate HTTP traffic with intentional errors to trigger alerts."""
    print(f"🔄 Generating traffic with errors for {duration} seconds...")
    print("   (Mixing valid requests with error 400s to spike error rate)\n")

    async with httpx.AsyncClient() as client:
        headers = {"X-API-Key": os.getenv("API_KEY", "api_key")}
        start = time.time()
        request_count = 0
        
        # Date range for forecast requests
        start_date = "2025-02-10"
        end_date = "2025-02-17"

        while time.time() - start < duration:
            try:
                # 70% valid requests
                if request_count % 10 < 7:
                    await client.get(
                        f"{api_url}/api/v1/forecast",
                        params={
                            "id_well": "POZO-001",
                            "date_start": start_date,
                            "date_end": end_date,
                        },
                        headers=headers,
                        timeout=5.0,
                    )
                else:
                    # 30% error requests (invalid well - returns 404)
                    await client.get(
                        f"{api_url}/api/v1/forecast",
                        params={
                            "id_well": "INVALID-WELL",
                            "date_start": start_date,
                            "date_end": end_date,
                        },
                        headers=headers,
                        timeout=5.0,
                    )

                request_count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"  Request error: {type(e).__name__}")

    print(f"✅ Generated {request_count} requests\n")


async def main():
    """Test Slack integration."""
    print("=" * 70)
    print("SLACK ALERT TEST - Verify alerts are sent to Slack")
    print("=" * 70 + "\n")

    # 1. Verify Slack webhook is configured
    import os
    from dotenv import load_dotenv

    load_dotenv()
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url or not webhook_url.strip():
        print("❌ ERROR: SLACK_WEBHOOK_URL not configured in .env")
        print("   Add: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...\n")
        return

    print(f"✅ Slack webhook configured\n")

    # 2. Generate traffic
    await generate_traffic_with_errors()

    # 3. Wait for Prometheus to scrape
    print("⏳ Waiting for Prometheus scrape (6 seconds)...")
    await asyncio.sleep(6)
    print("✅ Ready\n")

    # 4. Create metrics provider
    prometheus_provider = PrometheusMetricsProvider()

    # 5. Display metrics
    print("📊 Current Metrics from Prometheus:")
    avg_latency = prometheus_provider.get_average_latency()
    error_rate = prometheus_provider.get_error_rate()
    request_count = prometheus_provider.get_request_count_last_seconds(30)

    print(
        f"  Average Latency:  {avg_latency:.4f}s"
        if avg_latency
        else "  Average Latency:  No data"
    )
    print(
        f"  Error Rate:       {error_rate*100:.2f}%"
        if error_rate
        else "  Error Rate:       No data"
    )
    print(f"  Request Count:    {request_count} requests/30s\n")

    # 6. Create scheduler with SlackNotifier
    print("🚀 Creating alerts with SlackNotifier...\n")

    config = AlertConfig(
        latency_threshold=0.1,  # 100ms (likely to trigger)
        error_rate_threshold=0.05,  # 5% error rate
        service_down_threshold=30,
    )

    detectors = [
        LatencyDetector(config),
        ErrorRateDetector(config),
        ServiceDownDetector(config),
    ]

    # This will send to Slack
    slack_notifier = SlackNotifier(webhook_url=webhook_url)
    scheduler = AlertScheduler(config, slack_notifier, detectors)

    # 7. Run detectors (this will send alerts to Slack)
    print("🔍 Running alert detectors and sending to Slack...\n")
    await scheduler.check_alerts(prometheus_provider)

    print("=" * 70)
    print("✅ Check your Slack channel for alerts!")
    print("\n📍 Links:")
    print("   • Dashboard: http://localhost:3000")
    print("   • Prometheus: http://localhost:9090")
    print("   • API Docs:   http://localhost:8000/docs")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())