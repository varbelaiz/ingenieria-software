"""Load deterministic bronze fixtures so silver dbt models can run in CI.

Reuses the production bronze loader (``load_bronze_table``) and warehouse
connection instead of ``dbt seed``: ``dbt build`` would otherwise run seeds by
default and the end-to-end orchestration (extraction -> ``dbt build``) would
overwrite the real bronze data.
"""

from __future__ import annotations

from typing import Any

from data_platform.extraction.bronze_loader import BronzeLoad, load_bronze_table
from data_platform.orchestration.assets.bronze import warehouse_connection


LOAD_PERIOD = "2024-01"

# Ultimo dia de cada mes de 2024 (bisiesto) para fecha_data y dias_produccion.
_LAST_DAY = {
    1: 31,
    2: 29,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}

# Serie mensual determinista por pozo (Ene..Dic 2024). El gas declina con un
# wobble NO constante a proposito: el OLS gas(t)->gas(t+1) no ajusta perfecto,
# asi MAE/RMSE > 0 y difieren entre cortes (p.ej. 2024-06-30 vs 2024-12-31).
_WELLS: list[dict[str, Any]] = [
    {
        "idpozo": "135204",
        "idempresa": "YPF",
        "empresa": "YPF S.A.",
        "area": "Loma Campana",
        "cuenca": "Neuquina",
        "tipo_recurso": "SHALE",
        "gas": [
            59.94,
            58.10,
            55.30,
            53.80,
            50.20,
            49.10,
            46.00,
            45.30,
            42.10,
            41.50,
            39.00,
            38.20,
        ],
        "oil": [
            120.50,
            118.00,
            112.40,
            109.10,
            103.70,
            99.80,
            95.20,
            92.60,
            88.00,
            85.30,
            81.10,
            78.90,
        ],
        "water": [
            10.00,
            9.50,
            9.20,
            8.80,
            8.50,
            8.10,
            7.90,
            7.40,
            7.10,
            6.80,
            6.50,
            6.20,
        ],
    },
    {
        "idpozo": "200001",
        "idempresa": "PAMPA",
        "empresa": "Pampa Energia",
        "area": "El Mangrullo",
        "cuenca": "Neuquina",
        "tipo_recurso": "TIGHT",
        "gas": [
            40.00,
            38.50,
            37.80,
            35.10,
            34.60,
            32.00,
            31.40,
            29.90,
            28.10,
            27.50,
            25.80,
            25.10,
        ],
        "oil": [
            80.00,
            78.30,
            75.10,
            72.60,
            70.20,
            67.10,
            65.40,
            62.80,
            60.10,
            58.30,
            55.90,
            54.20,
        ],
        "water": [
            5.00,
            4.90,
            4.70,
            4.60,
            4.40,
            4.30,
            4.10,
            4.00,
            3.80,
            3.70,
            3.50,
            3.40,
        ],
    },
    {
        "idpozo": "300001",
        "idempresa": "CAPSA",
        "empresa": "CAPSA Petroleum",
        "area": "Cañadon Seco",
        "cuenca": "Golfo San Jorge",
        "tipo_recurso": "CONVENCIONAL",
        "gas": [
            12.00,
            11.80,
            11.50,
            11.30,
            11.00,
            10.90,
            10.60,
            10.50,
            10.20,
            10.10,
            9.80,
            9.70,
        ],
        "oil": [
            55.00,
            54.10,
            53.30,
            52.10,
            51.40,
            50.20,
            49.50,
            48.30,
            47.60,
            46.40,
            45.70,
            44.50,
        ],
        "water": [
            8.00,
            7.90,
            7.80,
            7.60,
            7.50,
            7.30,
            7.20,
            7.00,
            6.90,
            6.70,
            6.60,
            6.40,
        ],
    },
]


def _production_fixture() -> list[dict[str, str]]:
    """Expandir cada serie por pozo en filas bronze mensuales de 2024."""

    rows: list[dict[str, str]] = []
    for well in _WELLS:
        for index, month in enumerate(range(1, 13)):
            rows.append(
                {
                    "idempresa": str(well["idempresa"]),
                    "empresa": str(well["empresa"]),
                    "area": str(well["area"]),
                    "cuenca": str(well["cuenca"]),
                    "tipo_recurso": str(well["tipo_recurso"]),
                    "anio": "2024",
                    "mes": str(month),
                    "idpozo": str(well["idpozo"]),
                    "prod_pet": f"{well['oil'][index]:.3f}",
                    "prod_gas": f"{well['gas'][index]:.3f}",
                    "prod_agua": f"{well['water'][index]:.3f}",
                    "dias_produccion": str(_LAST_DAY[month]),
                    "fecha_data": f"2024-{month:02d}-{_LAST_DAY[month]:02d}",
                }
            )
    return rows


PRODUCCION_FIXTURE: list[dict[str, str]] = _production_fixture()

POZOS_FIXTURE: list[dict[str, str]] = [
    {
        "idpozo": "135204",
        "sigla": "APA.Nq.ACO-13(d)",
        "formprod": "FIMP",
        "idempresa": "YPF",
        "empresa": "YPF S.A.",
        "area": "Loma Campana",
        "cuenca": "Neuquina",
        "tipo_recurso": "SHALE",
        "fecha_data": "2024-01-31",
    },
    {
        "idpozo": "200001",
        "sigla": "PAM.Nq.X-1",
        "formprod": "VMUT",
        "idempresa": "PAMPA",
        "empresa": "Pampa Energia",
        "area": "El Mangrullo",
        "cuenca": "Neuquina",
        "tipo_recurso": "TIGHT",
        "fecha_data": "2024-01-31",
    },
    {
        "idpozo": "300001",
        "sigla": "CAP.GSJ.CS-1",
        "formprod": "CONV",
        "idempresa": "CAPSA",
        "empresa": "CAPSA Petroleum",
        "area": "Cañadon Seco",
        "cuenca": "Golfo San Jorge",
        "tipo_recurso": "CONVENCIONAL",
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
