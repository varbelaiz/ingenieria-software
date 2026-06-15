"""Central DbtProject for the dagster-dbt integration."""

from pathlib import Path

from dagster_dbt import DbtProject

REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = REPO_ROOT / "data_platform" / "transform"

dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
)
# In dev this generates target/manifest.json on the fly; in CI/Docker the
# manifest is pre-generated at build time (see Dockerfile.dagster and ci.yml).
dbt_project.prepare_if_dev()
