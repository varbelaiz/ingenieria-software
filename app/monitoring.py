"""Minimal Prometheus-compatible metrics for technical monitoring."""

from __future__ import annotations

import os
import resource
import threading
from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter, time
from typing import Iterable

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

REQUEST_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@dataclass(frozen=True)
class MetricLabels:
    """Label set used to identify a request metric series."""

    method: str
    path: str
    status_code: str

    def to_prometheus(self) -> str:
        """Serialize labels using Prometheus exposition syntax."""
        return (
            f'method="{self.method}",'
            f'path="{self.path}",'
            f'status_code="{self.status_code}"'
        )


_REQUEST_COUNT: dict[MetricLabels, float] = defaultdict(float)
_ERROR_COUNT: dict[MetricLabels, float] = defaultdict(float)
_REQUEST_DURATION_COUNT: dict[MetricLabels, float] = defaultdict(float)
_REQUEST_DURATION_SUM: dict[MetricLabels, float] = defaultdict(float)
_REQUEST_DURATION_BUCKET_COUNTS: dict[MetricLabels, list[float]] = defaultdict(
    lambda: [0.0 for _ in REQUEST_DURATION_BUCKETS]
)
_LOCK = threading.Lock()
_PROCESS_START_TIME_SECONDS = time()

router = APIRouter(include_in_schema=False)


def start_timer() -> float:
    """Return a monotonic timestamp to measure request duration."""
    return perf_counter()


def normalize_path(raw_path: str) -> str:
    """Collapse paths that are irrelevant to business monitoring."""
    if raw_path.startswith("/docs"):
        return "/docs"
    return raw_path


def observe_request(
    method: str, path: str, status_code: int, started_at: float
) -> None:
    """Record counters and latency for a completed HTTP request."""
    labels = MetricLabels(
        method=method,
        path=normalize_path(path),
        status_code=str(status_code),
    )
    duration = perf_counter() - started_at

    with _LOCK:
        _REQUEST_COUNT[labels] += 1
        _REQUEST_DURATION_COUNT[labels] += 1
        _REQUEST_DURATION_SUM[labels] += duration

        for index, bucket_upper_bound in enumerate(REQUEST_DURATION_BUCKETS):
            if duration <= bucket_upper_bound:
                _REQUEST_DURATION_BUCKET_COUNTS[labels][index] += 1

        if status_code >= 400:
            _ERROR_COUNT[labels] += 1


def _prometheus_lines() -> list[str]:
    """Render all metric series in Prometheus text exposition format."""
    lines = [
        (
            "# HELP forecast_api_requests_total Total HTTP requests handled "
            "by the API."
        ),
        "# TYPE forecast_api_requests_total counter",
    ]

    with _LOCK:
        request_series = sorted(
            _REQUEST_COUNT.items(),
            key=lambda item: item[0].to_prometheus(),
        )
        error_series = sorted(
            _ERROR_COUNT.items(),
            key=lambda item: item[0].to_prometheus(),
        )
        histogram_labels = sorted(
            _REQUEST_DURATION_COUNT.keys(),
            key=lambda labels: labels.to_prometheus(),
        )

    for labels, count in request_series:
        label_text = labels.to_prometheus()
        lines.append(f"forecast_api_requests_total{{{label_text}}} " f"{count:.0f}")

    lines.extend(
        [
            (
                "# HELP forecast_api_errors_total Total HTTP error responses "
                "returned by the API."
            ),
            "# TYPE forecast_api_errors_total counter",
        ]
    )
    for labels, count in error_series:
        label_text = labels.to_prometheus()
        lines.append(f"forecast_api_errors_total{{{label_text}}} {count:.0f}")

    lines.extend(
        [
            (
                "# HELP forecast_api_request_duration_seconds HTTP request "
                "latency in seconds."
            ),
            "# TYPE forecast_api_request_duration_seconds histogram",
        ]
    )
    with _LOCK:
        for labels in histogram_labels:
            bucket_counts = _REQUEST_DURATION_BUCKET_COUNTS[labels]
            cumulative = 0.0
            label_text = labels.to_prometheus()

            for bucket_upper_bound, bucket_count in zip(
                REQUEST_DURATION_BUCKETS, bucket_counts
            ):
                cumulative += bucket_count
                lines.append(
                    "forecast_api_request_duration_seconds_bucket"
                    f'{{{label_text},le="{bucket_upper_bound}"}} '
                    f"{cumulative:.0f}"
                )

            total_count = _REQUEST_DURATION_COUNT[labels]
            label_text = labels.to_prometheus()
            lines.append(
                "forecast_api_request_duration_seconds_bucket"
                f'{{{label_text},le="+Inf"}} {total_count:.0f}'
            )
            lines.append(
                "forecast_api_request_duration_seconds_count"
                f"{{{label_text}}} {total_count:.0f}"
            )
            lines.append(
                "forecast_api_request_duration_seconds_sum"
                f"{{{label_text}}} {_REQUEST_DURATION_SUM[labels]}"
            )

    lines.extend(_process_metric_lines())
    return lines


def _process_metric_lines() -> Iterable[str]:
    """Expose lightweight process metrics without external dependencies."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    resident_memory_bytes = _resident_memory_bytes(usage.ru_maxrss)
    cpu_seconds = usage.ru_utime + usage.ru_stime

    return [
        "# HELP process_resident_memory_bytes Resident memory size in bytes.",
        "# TYPE process_resident_memory_bytes gauge",
        (
            f'process_resident_memory_bytes{{pid="{os.getpid()}"}} '
            f"{resident_memory_bytes}"
        ),
        (
            "# HELP process_cpu_seconds_total Total user and system CPU time "
            "spent in seconds."
        ),
        "# TYPE process_cpu_seconds_total counter",
        (f'process_cpu_seconds_total{{pid="{os.getpid()}"}} ' f"{cpu_seconds}"),
        (
            "# HELP process_start_time_seconds Start time of the process "
            "since unix epoch in seconds."
        ),
        "# TYPE process_start_time_seconds gauge",
        (
            f'process_start_time_seconds{{pid="{os.getpid()}"}} '
            f"{_PROCESS_START_TIME_SECONDS}"
        ),
    ]


def _resident_memory_bytes(ru_maxrss: int) -> int:
    """Normalize ru_maxrss across macOS and Linux."""
    if os.name == "posix" and os.uname().sysname == "Darwin":
        return ru_maxrss
    return ru_maxrss * 1024


@router.get("/metrics")
def metrics() -> PlainTextResponse:
    """Expose Prometheus-compatible metrics for local monitoring."""
    return PlainTextResponse(
        content="\n".join(_prometheus_lines()) + "\n",
        media_type=METRICS_CONTENT_TYPE,
    )
