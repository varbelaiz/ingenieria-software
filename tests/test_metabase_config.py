"""Unit tests for the declarative Metabase BI configuration.

These run without a warehouse or a running Metabase: they validate the structural
integrity of the cards and dashboard defined in
:mod:`data_platform.bi.metabase_config`.
"""

from __future__ import annotations

import pytest

from data_platform.bi import metabase_config
from data_platform.bi.metabase_config import (
    DISPLAY_LINE,
    DISPLAY_SCALAR,
    DISPLAY_TABLE,
    PERIOD_FILTER_PLACEHOLDER,
    VALID_DISPLAYS,
)


def test_card_names_are_unique() -> None:
    """Each card has a distinct name (provisioning matches by name)."""
    names = [card.name for card in metabase_config.CARDS]
    assert len(names) == len(set(names))


def test_every_card_queries_the_gold_schema() -> None:
    """Cards have non-empty SQL that reads from the gold layer."""
    for card in metabase_config.CARDS:
        assert card.sql.strip(), f"{card.name} has empty SQL"
        assert "gold." in card.sql, f"{card.name} does not read from the gold schema"


def test_every_card_has_a_valid_display() -> None:
    """Cards use a supported Metabase visualization type."""
    for card in metabase_config.CARDS:
        assert card.display in VALID_DISPLAYS


def test_graph_cards_define_axes_and_others_do_not() -> None:
    """Charts map dimensions and metrics; tables and scalars carry no axis settings."""
    for card in metabase_config.CARDS:
        settings = card.visualization_settings()
        if card.display in (DISPLAY_TABLE, DISPLAY_SCALAR):
            assert "graph.dimensions" not in settings
            assert "graph.metrics" not in settings
            assert not card.dimensions
            assert not card.metrics
        else:
            assert card.dimensions, f"{card.name} is a chart without dimensions"
            assert card.metrics, f"{card.name} is a chart without metrics"
            assert settings["graph.dimensions"] == list(card.dimensions)
            assert settings["graph.metrics"] == list(card.metrics)


def test_scalar_cards_are_single_value_kpis() -> None:
    """The KPI cards render as scalars over the gold layer with empty settings."""
    expected = {
        "Producción acumulada de gas",
        "Producción acumulada de petróleo",
        "Pozos activos en el último mes",
        "Último período cargado",
    }
    scalars = {
        card.name for card in metabase_config.CARDS if card.display == DISPLAY_SCALAR
    }
    assert scalars == expected
    for name in expected:
        card = metabase_config.get_card(name)
        assert not card.visualization_settings()
        assert "gold." in card.sql


def test_tipo_recurso_card_splits_by_resource_type() -> None:
    """A line card breaks production down by tipo de recurso."""
    card = metabase_config.get_card("Producción por tipo de recurso")
    assert card.display == DISPLAY_LINE
    assert "gold.dim_tipo_recurso" in card.sql
    assert card.dimensions == ("periodo", "tipo_recurso")


def test_date_filter_placeholder_matches_opt_in_flag() -> None:
    """A card embeds the date filter placeholder iff it opts into the date filter."""
    for card in metabase_config.CARDS:
        has_placeholder = PERIOD_FILTER_PLACEHOLDER in card.sql
        assert has_placeholder == card.date_filtered, card.name


def test_unfiltered_cards_are_freshness_and_quality() -> None:
    """KPIs meant as 'latest' signals and the quality table ignore the date filter."""
    unfiltered = {card.name for card in metabase_config.CARDS if not card.date_filtered}
    assert unfiltered == {
        "Pozos activos en el último mes",
        "Último período cargado",
        "Marca de calidad de los datos",
    }


def test_date_filtered_cards_keep_fct_unaliased_in_outer_query() -> None:
    """Field filters reference the physical table, so the outer fct is not aliased.

    A CTE may still alias fct in its own scope (the filter never expands there); what
    matters is that the query the filter lands in selects from an un-aliased
    ``gold.fct_produccion`` and never aliases it on the same line as the ``where``.
    """
    for card in metabase_config.CARDS:
        if not card.date_filtered:
            continue
        # The field filter expands to "gold"."fct_produccion"."periodo"; an outer
        # alias would shadow that and break the query when a value is applied.
        assert "from gold.fct_produccion\n" in card.sql, card.name
        assert metabase_config.PERIOD_FILTER_PLACEHOLDER in card.sql, card.name


def test_validation_sql_renders_filter_placeholder_as_noop() -> None:
    """The placeholder is rendered to a tautology for offline SQL validation."""
    card = metabase_config.get_card("Producción de gas por cuenca")
    rendered = metabase_config.sql_for_validation(card)
    assert PERIOD_FILTER_PLACEHOLDER not in rendered
    assert "where true" in rendered


def test_secondary_axis_metrics_are_emitted_as_series_settings() -> None:
    """Metrics pinned to the right axis surface in series_settings."""
    card = metabase_config.get_card("Evolución mensual de producción total")
    assert card.right_axis_metrics == ("prod_petroleo", "prod_agua")
    series_settings = card.visualization_settings()["series_settings"]
    assert series_settings == {
        "prod_petroleo": {"axis": "right"},
        "prod_agua": {"axis": "right"},
    }


def test_petroleo_card_buckets_minor_operadoras() -> None:
    """The petróleo card groups the long tail of operadoras into 'Otras'."""
    card = metabase_config.get_card("Producción de petróleo por operadora")
    assert "'Otras'" in card.sql
    assert "row_number() over" in card.sql


def test_quality_card_has_conditional_formatting() -> None:
    """The quality table colours its status column by PASS/ERROR."""
    card = metabase_config.get_card("Marca de calidad de los datos")
    rules = card.visualization_settings()["table.column_formatting"]
    statuses = {rule["value"] for rule in rules}
    assert statuses == {"PASS", "ERROR"}
    for rule in rules:
        assert rule["columns"] == ["status"]


def test_exactly_one_card_is_full_width() -> None:
    """Only the quality table spans the full dashboard width."""
    full_width = [card.name for card in metabase_config.CARDS if card.full_width]
    assert full_width == ["Marca de calidad de los datos"]


def test_dashboard_references_only_existing_cards() -> None:
    """Every card referenced by the dashboard is a defined card."""
    available = metabase_config.card_names()
    assert metabase_config.DASHBOARD.card_names
    for name in metabase_config.DASHBOARD.card_names:
        assert name in available


def test_quality_mark_card_is_present() -> None:
    """The data quality mark is exposed as a table over gold.quality_marks."""
    quality = metabase_config.get_card("Marca de calidad de los datos")
    assert "gold.quality_marks" in quality.sql
    assert quality.display == DISPLAY_TABLE


def test_get_card_raises_for_unknown_name() -> None:
    """Looking up an unknown card name raises KeyError."""
    with pytest.raises(KeyError):
        metabase_config.get_card("does-not-exist")
