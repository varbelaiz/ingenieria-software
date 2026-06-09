"""Shared CSV download helpers for datos.gob.ar resources."""

from __future__ import annotations

from collections.abc import Mapping
import csv
from dataclasses import dataclass
import io

import httpx


@dataclass(frozen=True)
class CsvResource:
    """Metadata required to download and trace a CSV resource."""

    name: str
    url: str
    resource_id: str


class ExtractionError(RuntimeError):
    """Raised when a source resource cannot be downloaded or parsed."""


def download_csv_rows(
    resource: CsvResource,
    *,
    timeout_seconds: float = 30.0,
    max_attempts: int = 3,
    transport: httpx.BaseTransport | None = None,
) -> list[dict[str, str]]:
    """Download a CSV resource and return rows keyed by normalized headers."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_error: Exception | None = None
    for _attempt in range(1, max_attempts + 1):
        try:
            if transport is None:
                client = httpx.Client(
                    follow_redirects=True,
                    timeout=timeout_seconds,
                )
            else:
                client = httpx.Client(
                    follow_redirects=True,
                    timeout=timeout_seconds,
                    transport=transport,
                )
            with client:
                response = client.get(resource.url)
                response.raise_for_status()
                return _parse_csv_response(response.content)
        except (httpx.HTTPError, csv.Error, UnicodeDecodeError) as exc:
            last_error = exc

    message = f"Failed to download {resource.name} from {resource.url}"
    raise ExtractionError(message) from last_error


def _parse_csv_response(content: bytes) -> list[dict[str, str]]:
    """Parse UTF-8 CSV content, stripping BOM from the first header."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ExtractionError("CSV response does not include a header row")

    fieldnames = [_normalize_header(header) for header in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        rows.append(_normalize_row(raw_row, fieldnames))
    return rows


def _normalize_header(header: str) -> str:
    return header.lstrip("\ufeff").strip()


def _normalize_row(
    raw_row: Mapping[str, str | None],
    fieldnames: list[str],
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for original_key, normalized_key in zip(raw_row.keys(), fieldnames):
        value = raw_row[original_key]
        normalized[normalized_key] = "" if value is None else value
    return normalized
