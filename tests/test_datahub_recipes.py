"""Contract tests for DataHub ingestion recipes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


RECIPES_DIR = Path("data_platform/governance/recipes")


def load_recipe(name: str) -> dict[str, Any]:
    """Load a governance recipe as a YAML mapping."""
    recipe_path = RECIPES_DIR / name

    with recipe_path.open(encoding="utf-8") as recipe_file:
        recipe = yaml.safe_load(recipe_file)

    assert isinstance(recipe, dict)
    return recipe


def test_all_governance_recipes_are_valid_yaml_mappings() -> None:
    """Every governance recipe file should parse as a YAML mapping."""
    recipe_paths = sorted(RECIPES_DIR.rglob("*.yml"))

    assert {path.relative_to(RECIPES_DIR).as_posix() for path in recipe_paths} == {
        "ci/dbt.yml",
        "ci/postgres.yml",
        "dagster.yml",
        "dbt.yml",
        "postgres.yml",
    }

    for recipe_path in recipe_paths:
        with recipe_path.open(encoding="utf-8") as recipe_file:
            recipe = yaml.safe_load(recipe_file)

        message = f"{recipe_path} must parse to a YAML mapping"
        assert isinstance(recipe, dict), message


def test_postgres_recipe_defines_datahub_source_and_rest_sink() -> None:
    """The Postgres recipe should be executable by DataHub ingest."""
    recipe = load_recipe("postgres.yml")

    assert recipe["source"]["type"] == "postgres"
    assert isinstance(recipe["source"]["config"], dict)
    assert recipe["source"]["config"]["host_port"] == "localhost:5433"
    assert recipe["source"]["config"]["database"] == "warehouse"
    assert recipe["source"]["config"]["schema_pattern"]["allow"] == [
        "bronze",
        "silver",
        "gold",
        "dbt_test_failures",
    ]
    assert recipe["sink"]["type"] == "datahub-rest"
    assert recipe["sink"]["config"]["server"] == "http://localhost:8080"


def test_dbt_recipe_defines_datahub_source_and_rest_sink() -> None:
    """The dbt recipe should target generated dbt artifacts."""
    recipe = load_recipe("dbt.yml")

    assert recipe["source"]["type"] == "dbt"
    assert isinstance(recipe["source"]["config"], dict)
    assert recipe["source"]["config"]["manifest_path"] == (
        "data_platform/transform/target/manifest.json"
    )
    assert recipe["source"]["config"]["catalog_path"] == (
        "data_platform/transform/target/catalog.json"
    )
    assert recipe["source"]["config"]["sources_path"] == (
        "data_platform/transform/target/sources.json"
    )
    assert recipe["source"]["config"]["run_results_paths"] == [
        "data_platform/transform/target/run_results.json",
    ]
    assert recipe["source"]["config"]["target_platform"] == "postgres"
    assert "write_semantics" not in recipe["source"]["config"]
    assert recipe["sink"]["type"] == "datahub-rest"
    assert recipe["sink"]["config"]["server"] == "http://localhost:8080"


def test_ci_postgres_recipe_uses_file_sink() -> None:
    """CI should validate Postgres ingestion without connecting to DataHub GMS."""
    recipe = load_recipe("ci/postgres.yml")

    assert recipe["source"]["type"] == "postgres"
    assert recipe["source"]["config"]["host_port"] == "localhost:5433"
    assert recipe["sink"]["type"] == "file"
    assert recipe["sink"]["config"]["filename"] == (
        "/tmp/datahub-postgres-metadata.json"
    )


def test_ci_dbt_recipe_uses_file_sink() -> None:
    """CI should validate dbt ingestion without connecting to DataHub GMS."""
    recipe = load_recipe("ci/dbt.yml")

    assert recipe["source"]["type"] == "dbt"
    assert recipe["source"]["config"]["manifest_path"] == (
        "data_platform/transform/target/manifest.json"
    )
    assert recipe["source"]["config"]["write_semantics"] == "OVERRIDE"
    assert recipe["sink"]["type"] == "file"
    assert recipe["sink"]["config"]["filename"] == "/tmp/datahub-dbt-metadata.json"


def test_dagster_recipe_documents_expected_sensor_configuration() -> None:
    """Dagster metadata should be emitted through DataHub's Dagster sensor."""
    recipe = load_recipe("dagster.yml")

    sensor = recipe["dagster_sensor"]
    assert sensor["package"] == "acryl_datahub_dagster_plugin"
    assert sensor["sensor_name"] == "datahub_sensor"
    assert sensor["datahub"]["server"] == "http://localhost:8080"
    assert sensor["dagster"]["url"] == "http://localhost:3001"
    assert sensor["capture"] == {
        "asset_materialization": True,
        "input_output": True,
    }
    definitions_module = sensor["expected_definitions_module"]
    assert definitions_module == "data_platform.orchestration"
