"""Tests for datos.gob.ar extraction clients."""

import httpx
import pytest

from data_platform.extraction.client import (
    CsvResource,
    ExtractionError,
    download_csv_rows,
)


def test_download_csv_rows_normalizes_bom_in_headers() -> None:
    """It should strip a UTF-8 BOM from the first CSV header."""
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            content=(
                "\ufeffidpozo,sigla,empresa\n"
                "135204,APA.Nq.ACO-13(d),YSUR ENERGIA ARGENTINA S.R.L.\n"
            ).encode("utf-8"),
        )
    )

    rows = download_csv_rows(
        CsvResource(
            name="pozos",
            url="https://example.test/pozos.csv",
            resource_id="resource-pozos",
        ),
        transport=transport,
    )

    assert rows == [
        {
            "idpozo": "135204",
            "sigla": "APA.Nq.ACO-13(d)",
            "empresa": "YSUR ENERGIA ARGENTINA S.R.L.",
        }
    ]


def test_download_csv_rows_raises_clear_error_after_retries() -> None:
    """It should retry failed requests and raise an extraction error."""
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, text="temporarily unavailable")

    transport = httpx.MockTransport(handler)

    with pytest.raises(ExtractionError, match="Failed to download produccion"):
        download_csv_rows(
            CsvResource(
                name="produccion",
                url="https://example.test/produccion.csv",
                resource_id="resource-produccion",
            ),
            max_attempts=3,
            transport=transport,
        )

    assert attempts == 3
