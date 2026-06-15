"""dbt assets (silver/gold) integrated as Dagster assets."""

import json
from collections.abc import Iterator, Mapping
from typing import Any

from dagster import AssetExecutionContext, AssetKey
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

from data_platform.orchestration.assets.bronze import bronze_monthly_partitions
from data_platform.orchestration.dbt_project import dbt_project


class BronzeSourceTranslator(DagsterDbtTranslator):
    """Map dbt bronze sources to the keys of the bronze Dagster assets."""

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        """Return the Dagster AssetKey for a dbt resource.

        For dbt sources, maps to the corresponding bronze asset key using the
        convention ``bronze_<table_name>``. The project's only source schema is
        ``bronze`` (see sources.yml), so ``source_name`` is intentionally not part
        of the key. All other resource types fall back to the default
        DagsterDbtTranslator behaviour.
        """
        if dbt_resource_props["resource_type"] == "source":
            return AssetKey([f"bronze_{dbt_resource_props['name']}"])
        return super().get_asset_key(dbt_resource_props)


def build_dbt_build_args(partition_key: str | None) -> list[str]:
    """Build the ``dbt build`` args, injecting reprocess_period when partitioned."""
    args = ["build"]
    if partition_key is not None:
        args += ["--vars", json.dumps({"reprocess_period": partition_key})]
    return args


_translator = BronzeSourceTranslator()


@dbt_assets(
    manifest=dbt_project.manifest_path,
    partitions_def=bronze_monthly_partitions,
    dagster_dbt_translator=_translator,
)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource) -> Iterator[Any]:
    """Materialize silver/gold: run freshness (fail-fast) then dbt build."""
    # Stale sources block promotion before any transformation runs.
    dbt.cli(["source", "freshness"], raise_on_error=True).wait()

    partition_key = context.partition_key if context.has_partition_key else None
    yield from dbt.cli(build_dbt_build_args(partition_key), context=context).stream()
