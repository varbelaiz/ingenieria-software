"""Declarative, version-controlled definition of the Metabase BI assets.

This module is the reproducible "export" of the BI configuration: the warehouse
connection target, the questions (cards) that non-technical users consume and the
dashboard that groups them. It is pure data (standard library only) so it can be
imported and validated without a running Metabase or warehouse.

The companion module :mod:`data_platform.bi.provision` reads these definitions and
applies them idempotently against the Metabase REST API.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# All BI queries read exclusively from the gold layer of the warehouse.
WAREHOUSE_SCHEMA = "gold"

# Logical names used to make provisioning idempotent (lookups are by name).
WAREHOUSE_DATABASE_NAME = "Warehouse (gold)"
COLLECTION_NAME = "Plataforma de Datos - Pozos"

# Valid Metabase visualization types used by this configuration.
DISPLAY_LINE = "line"
DISPLAY_BAR = "bar"
DISPLAY_TABLE = "table"
VALID_DISPLAYS = frozenset({DISPLAY_LINE, DISPLAY_BAR, DISPLAY_TABLE})


@dataclass(frozen=True)
class Card:
    """A single Metabase question backed by a native SQL query over the gold layer."""

    name: str
    description: str
    sql: str
    display: str
    dimensions: tuple[str, ...] = field(default_factory=tuple)
    metrics: tuple[str, ...] = field(default_factory=tuple)

    def visualization_settings(self) -> dict[str, list[str]]:
        """Build Metabase ``visualization_settings`` for graph displays.

        Tables need no axis mapping; line and bar charts map result columns to the
        dimension (x axis / breakout) and metric (y axis) roles.
        """
        if self.display == DISPLAY_TABLE:
            return {}
        return {
            "graph.dimensions": list(self.dimensions),
            "graph.metrics": list(self.metrics),
        }


@dataclass(frozen=True)
class Dashboard:
    """A dashboard grouping a set of cards by name."""

    name: str
    description: str
    card_names: tuple[str, ...]


CARDS: tuple[Card, ...] = (
    Card(
        name="Producción de gas por cuenca",
        description=(
            "Gas producido por cuenca a lo largo del tiempo, para comparar la "
            "evolución entre cuencas."
        ),
        sql=(
            "select\n"
            "    f.periodo as periodo,\n"
            "    c.cuenca as cuenca,\n"
            "    sum(f.prod_gas) as prod_gas\n"
            "from gold.fct_produccion as f\n"
            "join gold.dim_cuenca as c on f.cuenca_key = c.cuenca_key\n"
            "group by f.periodo, c.cuenca\n"
            "order by f.periodo, c.cuenca"
        ),
        display=DISPLAY_LINE,
        dimensions=("periodo", "cuenca"),
        metrics=("prod_gas",),
    ),
    Card(
        name="Producción de petróleo por operadora",
        description=(
            "Petróleo producido por operadora a lo largo del tiempo, para ver el "
            "aporte de cada empresa."
        ),
        sql=(
            "select\n"
            "    f.periodo as periodo,\n"
            "    e.empresa as operadora,\n"
            "    sum(f.prod_petroleo) as prod_petroleo\n"
            "from gold.fct_produccion as f\n"
            "join gold.dim_empresa as e on f.empresa_key = e.empresa_key\n"
            "group by f.periodo, e.empresa\n"
            "order by f.periodo, e.empresa"
        ),
        display=DISPLAY_LINE,
        dimensions=("periodo", "operadora"),
        metrics=("prod_petroleo",),
    ),
    Card(
        name="Top pozos por producción acumulada",
        description=(
            "Los 20 pozos con mayor producción acumulada (gas + petróleo) en todo el "
            "período disponible."
        ),
        sql=(
            "select\n"
            "    p.sigla as pozo,\n"
            "    sum(f.prod_gas + f.prod_petroleo) as produccion_total\n"
            "from gold.fct_produccion as f\n"
            "join gold.dim_pozo as p on f.pozo_key = p.pozo_key\n"
            "group by p.sigla\n"
            "order by produccion_total desc\n"
            "limit 20"
        ),
        display=DISPLAY_BAR,
        dimensions=("pozo",),
        metrics=("produccion_total",),
    ),
    Card(
        name="Evolución mensual de producción total",
        description=(
            "Producción total mensual de gas, petróleo y agua sumando todos los pozos."
        ),
        sql=(
            "select\n"
            "    f.periodo as periodo,\n"
            "    sum(f.prod_gas) as prod_gas,\n"
            "    sum(f.prod_petroleo) as prod_petroleo,\n"
            "    sum(f.prod_agua) as prod_agua\n"
            "from gold.fct_produccion as f\n"
            "group by f.periodo\n"
            "order by f.periodo"
        ),
        display=DISPLAY_LINE,
        dimensions=("periodo",),
        metrics=("prod_gas", "prod_petroleo", "prod_agua"),
    ),
    Card(
        name="Marca de calidad de los datos",
        description=(
            "Último estado de cada control de calidad sobre la capa gold. Revisar "
            "antes de publicar: un check en ERROR indica datos no confiables."
        ),
        sql=(
            "select\n"
            "    check_name,\n"
            "    dimension,\n"
            "    status,\n"
            "    failed_rows,\n"
            "    checked_at\n"
            "from gold.quality_marks\n"
            "order by status desc, check_name"
        ),
        display=DISPLAY_TABLE,
    ),
)


DASHBOARD = Dashboard(
    name="Producción de pozos no convencionales",
    description=(
        "Vista para usuarios no técnicos: producción por cuenca y operadora, top "
        "pozos, evolución mensual y la marca de calidad de los datos."
    ),
    card_names=tuple(card.name for card in CARDS),
)


def card_names() -> set[str]:
    """Return the set of all configured card names."""
    return {card.name for card in CARDS}


def get_card(name: str) -> Card:
    """Return the card with the given name, raising ``KeyError`` if missing."""
    for card in CARDS:
        if card.name == name:
            return card
    raise KeyError(name)
