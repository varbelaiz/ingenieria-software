"""Extraction client for the operator-submitted well list."""

from __future__ import annotations

import os

from data_platform.extraction.client import CsvResource, download_csv_rows


POZOS_RESOURCE_ID = "energia_cbfa4d79-ffb3-4096-bab5-eb0dde9a8385"
POZOS_DEFAULT_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-"
    "1ad3543b407c/resource/cbfa4d79-ffb3-4096-bab5-eb0dde9a8385/download/"
    "listado-de-pozos-cargados-por-empresas-operadoras.csv"
)
POZOS_URL_ENV = "POZOS_OPERADORAS_URL"


def fetch_pozos_rows() -> list[dict[str, str]]:
    """Download raw operator-submitted well rows."""
    resource = CsvResource(
        name="pozos",
        url=os.getenv(POZOS_URL_ENV, POZOS_DEFAULT_URL),
        resource_id=POZOS_RESOURCE_ID,
    )
    return download_csv_rows(resource)
