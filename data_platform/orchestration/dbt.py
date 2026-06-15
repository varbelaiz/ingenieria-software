"""Helpers to execute dbt quality builds from Dagster."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import shutil
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = REPO_ROOT / "data_platform" / "transform"
DBT_PROFILES_DIR = DBT_PROJECT_DIR
DBT_SELECT = "silver gold"


class DbtBuildFailedError(RuntimeError):
    """Raised when the dbt build process returns a non-zero exit code."""


CompletedProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


def build_dbt_build_command(
    *,
    select: str = DBT_SELECT,
    project_dir: Path = DBT_PROJECT_DIR,
    profiles_dir: Path = DBT_PROFILES_DIR,
) -> list[str]:
    """Build the canonical dbt build command used by orchestration."""
    dbt_executable = shutil.which("dbt") or "dbt"
    return [
        dbt_executable,
        "build",
        "--select",
        select,
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(profiles_dir),
    ]


def build_dbt_source_freshness_command(
    *,
    project_dir: Path = DBT_PROJECT_DIR,
    profiles_dir: Path = DBT_PROFILES_DIR,
) -> list[str]:
    """Build the canonical dbt source freshness command used by orchestration."""
    dbt_executable = shutil.which("dbt") or "dbt"
    return [
        dbt_executable,
        "source",
        "freshness",
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(profiles_dir),
    ]


def run_dbt_build(
    command: Sequence[str] | None = None,
    *,
    runner: CompletedProcessRunner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Run dbt build and fail fast when quality checks do not pass."""
    build_command = list(command) if command is not None else build_dbt_build_command()
    completed = runner(
        build_command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise DbtBuildFailedError(
            "dbt build failed with exit code "
            f"{completed.returncode}: {completed.stderr or completed.stdout}"
        )
    return completed


def run_dbt_source_freshness(
    command: Sequence[str] | None = None,
    *,
    runner: CompletedProcessRunner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Run dbt source freshness and fail fast when sources are stale."""
    freshness_command = (
        list(command) if command is not None else build_dbt_source_freshness_command()
    )
    completed = runner(
        freshness_command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise DbtBuildFailedError(
            "dbt source freshness failed with exit code "
            f"{completed.returncode}: {completed.stderr or completed.stdout}"
        )
    return completed
