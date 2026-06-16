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
from typing import Any

# All BI queries read exclusively from the gold layer of the warehouse.
WAREHOUSE_SCHEMA = "gold"

# Logical names used to make provisioning idempotent (lookups are by name).
WAREHOUSE_DATABASE_NAME = "Warehouse (gold)"
COLLECTION_NAME = "Plataforma de Datos - Pozos"

# Valid Metabase visualization types used by this configuration.
DISPLAY_LINE = "line"
DISPLAY_BAR = "bar"
DISPLAY_TABLE = "table"
DISPLAY_SCALAR = "scalar"
VALID_DISPLAYS = frozenset({DISPLAY_LINE, DISPLAY_BAR, DISPLAY_TABLE, DISPLAY_SCALAR})

# Single dashboard-level date range filter. Cards that opt in (``date_filtered``)
# embed this Metabase field-filter placeholder in their SQL; the provisioner wires
# it to a ``date/all-options`` parameter on the dashboard. Field filters generate a
# fully-qualified ``"gold"."fct_produccion"."periodo"`` reference, so opted-in cards
# must keep ``gold.fct_produccion`` un-aliased in their outer query.
PERIOD_FILTER_TAG = "periodo_filter"
PERIOD_FILTER_PLACEHOLDER = "{{" + PERIOD_FILTER_TAG + "}}"


@dataclass(frozen=True)
class ColumnFormatRule:
    """A single conditional-formatting rule for a Metabase table column.

    Maps to one entry of ``table.column_formatting``: when ``column`` satisfies
    ``operator``/``value`` the cell (or whole row, if ``highlight_row``) is painted
    with ``color``.
    """

    column: str
    operator: str
    value: str
    color: str
    highlight_row: bool = False

    def to_metabase(self) -> dict[str, Any]:
        """Render this rule as a Metabase ``table.column_formatting`` entry."""
        return {
            "columns": [self.column],
            "type": "single",
            "operator": self.operator,
            "value": self.value,
            "color": self.color,
            "highlight_row": self.highlight_row,
        }


@dataclass(frozen=True)
class Card:  # pylint: disable=too-many-instance-attributes
    """A single Metabase question backed by a native SQL query over the gold layer."""

    name: str
    description: str
    sql: str
    display: str
    dimensions: tuple[str, ...] = field(default_factory=tuple)
    metrics: tuple[str, ...] = field(default_factory=tuple)
    # Metrics to plot on the secondary (right) Y axis; only meaningful for charts.
    right_axis_metrics: tuple[str, ...] = field(default_factory=tuple)
    # Conditional-formatting rules; only meaningful for table displays.
    conditional_formats: tuple[ColumnFormatRule, ...] = field(default_factory=tuple)
    # Whether this card spans the full dashboard width instead of half.
    full_width: bool = False
    # Whether this card participates in the dashboard-level date range filter.
    date_filtered: bool = False

    def visualization_settings(self) -> dict[str, Any]:
        """Build Metabase ``visualization_settings`` for this card's display.

        Scalars carry no axis settings. Tables optionally carry conditional-formatting
        rules; line and bar charts map result columns to the dimension (x axis /
        breakout) and metric (y axis) roles, and may pin some metrics to the secondary
        (right) axis.
        """
        if self.display == DISPLAY_SCALAR:
            return {}
        if self.display == DISPLAY_TABLE:
            if not self.conditional_formats:
                return {}
            return {
                "table.column_formatting": [
                    rule.to_metabase() for rule in self.conditional_formats
                ]
            }
        settings: dict[str, Any] = {
            "graph.dimensions": list(self.dimensions),
            "graph.metrics": list(self.metrics),
        }
        if self.right_axis_metrics:
            settings["series_settings"] = {
                metric: {"axis": "right"} for metric in self.right_axis_metrics
            }
        return settings


@dataclass(frozen=True)
class Dashboard:
    """A dashboard grouping a set of cards by name."""

    name: str
    description: str
    card_names: tuple[str, ...]


CARDS: tuple[Card, ...] = (
    Card(
        name="Producción acumulada de gas",
        description=(
            "Gas total producido en el período seleccionado (responde al filtro de "
            "fecha del dashboard)."
        ),
        sql=(
            "select sum(fct_produccion.prod_gas) as gas_acumulado\n"
            "from gold.fct_produccion\n"
            "where " + PERIOD_FILTER_PLACEHOLDER
        ),
        display=DISPLAY_SCALAR,
        date_filtered=True,
    ),
    Card(
        name="Producción acumulada de petróleo",
        description=(
            "Petróleo total producido en el período seleccionado (responde al filtro "
            "de fecha del dashboard)."
        ),
        sql=(
            "select sum(fct_produccion.prod_petroleo) as petroleo_acumulado\n"
            "from gold.fct_produccion\n"
            "where " + PERIOD_FILTER_PLACEHOLDER
        ),
        display=DISPLAY_SCALAR,
        date_filtered=True,
    ),
    Card(
        name="Pozos activos en el último mes",
        description=(
            "Cantidad de pozos con producción (gas o petróleo) en el último mes "
            "cargado. Indicador de actividad; no se ve afectado por el filtro de fecha."
        ),
        sql=(
            "select count(distinct fct_produccion.id_pozo) as pozos_activos\n"
            "from gold.fct_produccion\n"
            "where fct_produccion.periodo = "
            "(select max(periodo) from gold.fct_produccion)\n"
            "    and (fct_produccion.prod_gas + fct_produccion.prod_petroleo) > 0"
        ),
        display=DISPLAY_SCALAR,
    ),
    Card(
        name="Último período cargado",
        description=(
            "Mes más reciente con datos en la capa gold. Señal de frescura; siempre "
            "muestra el último período real, sin importar el filtro de fecha."
        ),
        sql=(
            "select max(fct_produccion.periodo) as ultimo_periodo\n"
            "from gold.fct_produccion"
        ),
        display=DISPLAY_SCALAR,
    ),
    Card(
        name="Producción de gas por cuenca",
        description=(
            "Gas producido por cuenca a lo largo del tiempo, para comparar la "
            "evolución entre cuencas."
        ),
        sql=(
            "select\n"
            "    fct_produccion.periodo as periodo,\n"
            "    c.cuenca as cuenca,\n"
            "    sum(fct_produccion.prod_gas) as prod_gas\n"
            "from gold.fct_produccion\n"
            "join gold.dim_cuenca as c "
            "on fct_produccion.cuenca_key = c.cuenca_key\n"
            "where " + PERIOD_FILTER_PLACEHOLDER + "\n"
            "group by fct_produccion.periodo, c.cuenca\n"
            "order by fct_produccion.periodo, c.cuenca"
        ),
        display=DISPLAY_LINE,
        dimensions=("periodo", "cuenca"),
        metrics=("prod_gas",),
        date_filtered=True,
    ),
    Card(
        name="Producción de petróleo por operadora",
        description=(
            "Petróleo producido por las 8 operadoras de mayor producción acumulada a "
            "lo largo del tiempo; el resto se agrupa en 'Otras'. Acotar las series "
            "mantiene el gráfico legible y evita el truncado de resultados."
        ),
        sql=(
            "with acumulado as (\n"
            "    select e.empresa as operadora, sum(f.prod_petroleo) as total\n"
            "    from gold.fct_produccion as f\n"
            "    join gold.dim_empresa as e on f.empresa_key = e.empresa_key\n"
            "    group by e.empresa\n"
            "),\n"
            "ranking as (\n"
            "    select operadora, row_number() over (order by total desc) as rn\n"
            "    from acumulado\n"
            "),\n"
            "etiqueta as (\n"
            "    select operadora,\n"
            "        case when rn <= 8 then operadora else 'Otras' end as grupo\n"
            "    from ranking\n"
            ")\n"
            "select\n"
            "    fct_produccion.periodo as periodo,\n"
            "    t.grupo as operadora,\n"
            "    sum(fct_produccion.prod_petroleo) as prod_petroleo\n"
            "from gold.fct_produccion\n"
            "join gold.dim_empresa as e "
            "on fct_produccion.empresa_key = e.empresa_key\n"
            "join etiqueta as t on t.operadora = e.empresa\n"
            "where " + PERIOD_FILTER_PLACEHOLDER + "\n"
            "group by fct_produccion.periodo, t.grupo\n"
            "order by fct_produccion.periodo, t.grupo"
        ),
        display=DISPLAY_LINE,
        dimensions=("periodo", "operadora"),
        metrics=("prod_petroleo",),
        date_filtered=True,
    ),
    Card(
        name="Producción por tipo de recurso",
        description=(
            "Producción total (gas + petróleo) separada por tipo de recurso "
            "(convencional vs. no convencional) a lo largo del tiempo. Da contexto al "
            "foco no convencional del dashboard."
        ),
        sql=(
            "select\n"
            "    fct_produccion.periodo as periodo,\n"
            "    tr.tipo_recurso as tipo_recurso,\n"
            "    sum(fct_produccion.prod_gas + fct_produccion.prod_petroleo) "
            "as produccion_total\n"
            "from gold.fct_produccion\n"
            "join gold.dim_tipo_recurso as tr "
            "on fct_produccion.tipo_recurso_key = tr.tipo_recurso_key\n"
            "where " + PERIOD_FILTER_PLACEHOLDER + "\n"
            "group by fct_produccion.periodo, tr.tipo_recurso\n"
            "order by fct_produccion.periodo, tr.tipo_recurso"
        ),
        display=DISPLAY_LINE,
        dimensions=("periodo", "tipo_recurso"),
        metrics=("produccion_total",),
        date_filtered=True,
    ),
    Card(
        name="Top pozos por producción acumulada",
        description=(
            "Los 20 pozos con mayor producción acumulada (gas + petróleo) en el "
            "período seleccionado."
        ),
        sql=(
            "select\n"
            "    p.sigla as pozo,\n"
            "    sum(fct_produccion.prod_gas + fct_produccion.prod_petroleo) "
            "as produccion_total\n"
            "from gold.fct_produccion\n"
            "join gold.dim_pozo as p on fct_produccion.pozo_key = p.pozo_key\n"
            "where " + PERIOD_FILTER_PLACEHOLDER + "\n"
            "group by p.sigla\n"
            "order by produccion_total desc\n"
            "limit 20"
        ),
        display=DISPLAY_BAR,
        dimensions=("pozo",),
        metrics=("produccion_total",),
        date_filtered=True,
    ),
    Card(
        name="Evolución mensual de producción total",
        description=(
            "Producción total mensual de gas, petróleo y agua sumando todos los pozos."
        ),
        sql=(
            "select\n"
            "    fct_produccion.periodo as periodo,\n"
            "    sum(fct_produccion.prod_gas) as prod_gas,\n"
            "    sum(fct_produccion.prod_petroleo) as prod_petroleo,\n"
            "    sum(fct_produccion.prod_agua) as prod_agua\n"
            "from gold.fct_produccion\n"
            "where " + PERIOD_FILTER_PLACEHOLDER + "\n"
            "group by fct_produccion.periodo\n"
            "order by fct_produccion.periodo"
        ),
        display=DISPLAY_LINE,
        dimensions=("periodo",),
        metrics=("prod_gas", "prod_petroleo", "prod_agua"),
        # Gas dwarfs petróleo/agua early on; move the smaller series to the right
        # axis so they stay readable instead of flattening against zero.
        right_axis_metrics=("prod_petroleo", "prod_agua"),
        date_filtered=True,
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
            "order by case when status = 'ERROR' then 0 else 1 end, check_name"
        ),
        display=DISPLAY_TABLE,
        full_width=True,
        conditional_formats=(
            # Whole row turns red when a check is in ERROR, green when it passes.
            ColumnFormatRule(
                column="status",
                operator="=",
                value="ERROR",
                color="#ED6E6E",
                highlight_row=True,
            ),
            ColumnFormatRule(
                column="status",
                operator="=",
                value="PASS",
                color="#84BB4C",
            ),
        ),
    ),
)


DASHBOARD = Dashboard(
    name="Producción de pozos no convencionales",
    description=(
        "Vista para usuarios no técnicos: KPIs de producción, producción por cuenca, "
        "operadora y tipo de recurso, top pozos, evolución mensual y la marca de "
        "calidad de los datos. El filtro de fecha acota el período de los gráficos."
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


def sql_for_validation(card: Card) -> str:
    """Return the card SQL with the date filter placeholder rendered as a no-op.

    Metabase replaces an unset field filter with a tautology; mirroring that here lets
    the SQL be EXPLAIN-checked against the warehouse without a live Metabase to expand
    the ``{{periodo_filter}}`` template tag.
    """
    return card.sql.replace(PERIOD_FILTER_PLACEHOLDER, "true")
