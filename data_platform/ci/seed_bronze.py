"""Load deterministic bronze fixtures so silver dbt models can run in CI.

Reuses the production bronze loader (``load_bronze_table``) and warehouse
connection instead of ``dbt seed``: ``dbt build`` would otherwise run seeds by
default and the end-to-end orchestration (extraction -> ``dbt build``) would
overwrite the real bronze data.
"""

from __future__ import annotations

from data_platform.extraction.bronze_loader import BronzeLoad, load_bronze_table
from data_platform.orchestration.assets.bronze import warehouse_connection


LOAD_PERIOD = "2024-01"

PRODUCCION_FIXTURE: list[dict[str, str]] = [
    {
        "idempresa": "YPF",
        "anio": "2024",
        "mes": "1",
        "idpozo": "135204",
        "prod_pet": "120.500",
        "prod_gas": "59.940",
        "prod_agua": "10.000",
        "fecha_data": "2024-01-31",
    },
    {
        "idempresa": "YPF",
        "anio": "2024",
        "mes": "2",
        "idpozo": "135204",
        "prod_pet": "118.000",
        "prod_gas": "58.100",
        "prod_agua": "9.500",
        "fecha_data": "2024-02-29",
    },
    {
        "idempresa": "PAMPA",
        "anio": "2024",
        "mes": "1",
        "idpozo": "200001",
        "prod_pet": "80.000",
        "prod_gas": "40.000",
        "prod_agua": "5.000",
        "fecha_data": "2024-01-31",
    },
]

POZOS_FIXTURE: list[dict[str, str]] = [
    {
        "idpozo": "135204",
        "sigla": "APA.Nq.ACO-13(d)",
        "formprod": "FIMP",
        "idempresa": "YPF",
        "fecha_data": "2024-01-31",
    },
    {
        "idpozo": "200001",
        "sigla": "PAM.Nq.X-1",
        "formprod": "VMUT",
        "idempresa": "PAMPA",
        "fecha_data": "2024-01-31",
    },
]


def seed_bronze() -> None:
    """Populate bronze tables with deterministic CI fixtures."""
    with warehouse_connection() as conn:
        load_bronze_table(
            conn,
            BronzeLoad(
                table_name="produccion_raw",
                load_period=LOAD_PERIOD,
                source_url="https://example.test/produccion.csv",
                resource_id="ci-produccion",
                rows=PRODUCCION_FIXTURE,
            ),
        )
        load_bronze_table(
            conn,
            BronzeLoad(
                table_name="pozos_raw",
                load_period=LOAD_PERIOD,
                source_url="https://example.test/pozos.csv",
                resource_id="ci-pozos",
                rows=POZOS_FIXTURE,
            ),
        )


if __name__ == "__main__":
    seed_bronze()
