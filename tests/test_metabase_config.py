"""Unit tests for the declarative Metabase BI configuration.

These run without a warehouse or a running Metabase: they validate the structural
integrity of the cards and dashboard defined in
:mod:`data_platform.bi.metabase_config`.
"""

from __future__ import annotations

import pytest

from data_platform.bi import metabase_config
from data_platform.bi.metabase_config import (
    DISPLAY_TABLE,
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


def test_graph_cards_define_axes_and_tables_do_not() -> None:
    """Charts map dimensions and metrics; tables carry no axis settings."""
    for card in metabase_config.CARDS:
        settings = card.visualization_settings()
        if card.display == DISPLAY_TABLE:
            assert "graph.dimensions" not in settings
            assert "graph.metrics" not in settings
            assert not card.dimensions
            assert not card.metrics
        else:
            assert card.dimensions, f"{card.name} is a chart without dimensions"
            assert card.metrics, f"{card.name} is a chart without metrics"
            assert settings["graph.dimensions"] == list(card.dimensions)
            assert settings["graph.metrics"] == list(card.metrics)


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
