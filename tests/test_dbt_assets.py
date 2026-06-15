"""Tests for dbt asset translator and argument builder."""

import json

from dagster import AssetKey

from data_platform.orchestration.assets.transform import (
    BronzeSourceTranslator,
    build_dbt_build_args,
)


def test_source_maps_to_bronze_asset_key() -> None:
    """dbt bronze sources should map to the matching bronze Dagster asset key."""
    translator = BronzeSourceTranslator()
    props = {
        "resource_type": "source",
        "name": "produccion_raw",
        "source_name": "bronze",
    }
    assert translator.get_asset_key(props) == AssetKey(["bronze_produccion_raw"])


def test_model_keeps_default_asset_key() -> None:
    """dbt models use schema-prefixed asset keys matching the real manifest."""
    translator = BronzeSourceTranslator()
    props = {
        "resource_type": "model",
        "name": "stg_produccion",
        "unique_id": "model.ingenieria_software.stg_produccion",
        "fqn": ["ingenieria_software", "silver", "stg_produccion"],
        "config": {"schema": "silver"},
        "meta": {},
        "version": None,
    }
    assert translator.get_asset_key(props) == AssetKey(["silver", "stg_produccion"])


def test_build_args_without_partition() -> None:
    """Without a partition key, build_dbt_build_args returns only ['build']."""
    assert build_dbt_build_args(None) == ["build"]


def test_build_args_with_partition_injects_reprocess_period() -> None:
    """With a partition key, reprocess_period is injected via --vars as JSON."""
    args = build_dbt_build_args("2026-05-01")
    assert args[:1] == ["build"]
    assert "--vars" in args
    vars_value = args[args.index("--vars") + 1]
    assert json.loads(vars_value) == {"reprocess_period": "2026-05-01"}
