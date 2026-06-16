"""Extraction client for non-conventional well production."""

from __future__ import annotations

import os

from data_platform.extraction.client import CsvResource, download_csv_rows


PRODUCCION_RESOURCE_ID = "energia_b5b58cdc-9e07-41f9-b392-fb9ec68b0725"
PRODUCCION_DEFAULT_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-"
    "1ad3543b407c/resource/b5b58cdc-9e07-41f9-b392-fb9ec68b0725/download/"
    "produccin-de-pozos-de-gas-y-petrleo-no-convencional.csv"
)
PRODUCCION_URL_ENV = "PRODUCCION_NO_CONVENCIONAL_URL"


def fetch_produccion_rows() -> list[dict[str, str]]:
    """Download raw non-conventional production rows."""
    resource = CsvResource(
        name="produccion",
        url=os.getenv(PRODUCCION_URL_ENV, PRODUCCION_DEFAULT_URL),
        resource_id=PRODUCCION_RESOURCE_ID,
    )
    return download_csv_rows(resource)
