# dagster-dbt Asset Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el op `run_end_to_end_dbt_build` (subprocess) por `@dbt_assets`, de modo que cada modelo dbt sea un asset de Dagster y el grafo muestre `bronze -> silver -> gold` granular con asset checks por test.

**Architecture:** Los assets de bronze (Python, ya existentes) siguen igual. Un `@dbt_assets` particionado mensual representa silver/gold; un `DagsterDbtTranslator` mapea las sources dbt a las claves de los assets bronze para conectar el grafo. Un asset job materializa todo; el schedule mensual lo dispara. El gate (dbt build corta downstream) y la alerta (failure hook) se preservan.

**Tech Stack:** dagster 1.13.8, dagster-dbt 0.29.8, dbt-postgres 1.8+, Postgres 16, Docker Compose. `dagster-dbt` ya está en `pyproject.toml` (grupo `data`).

**Worktree:** `/Users/varbelaiz/Code/Universidad/Software/ingenieria-software-dagster-dbt`, branch `feature/dagster-dbt-assets` (anidada sobre `fix/silver-source-column-mapping`). Todos los comandos corren desde el worktree.

---

## File Structure

- **Create** `data_platform/orchestration/dbt_project.py` — instancia `DbtProject` + `prepare_if_dev()`; única fuente del path del manifest.
- **Create** `data_platform/orchestration/assets/transform.py` — `DagsterDbtTranslator` (mapeo source->bronze), helper de args por partición, y la función `@dbt_assets`.
- **Modify** `data_platform/orchestration/jobs.py` — quitar ops de bronze, `run_end_to_end_dbt_build`, ops de calidad y `data_quality_job`; definir `end_to_end_data_job` como `define_asset_job`; conservar `data_quality_failure_hook` + helpers de alerta.
- **Modify** `data_platform/orchestration/__init__.py` — `Definitions` con bronze + dbt assets, recurso `dbt`, job y schedule; sin `data_quality_job`.
- **Modify** `data_platform/orchestration/schedules.py` — sin cambios de lógica (sigue importando `end_to_end_data_job` de `jobs`).
- **Delete** `data_platform/orchestration/dbt.py` — runner por subprocess (reemplazado por `DbtCliResource`).
- **Modify** `Dockerfile.dagster` — `dbt deps` + `dbt parse` para dejar `target/manifest.json` en la imagen.
- **Modify** `.github/workflows/ci.yml` — generar manifest antes de `dagster definitions validate`.
- **Modify** `tests/test_orchestration_jobs.py` — reescribir para el modelo asset-based.
- **Modify** `docs/ADRs/11-orchestration-tool.md`, `README.md`, `docs/runbooks/data-engineer.md` — reflejar el flujo asset-based.

---

### Task 1: `DbtProject` y plumbing del manifest

**Files:**
- Create: `data_platform/orchestration/dbt_project.py`
- Modify: `Dockerfile.dagster`
- Modify: `.github/workflows/ci.yml` (job `dagster-validate`)

- [ ] **Step 1: Crear el módulo `dbt_project.py`**

```python
"""DbtProject central para la integración dagster-dbt."""

from pathlib import Path

from dagster_dbt import DbtProject

REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = REPO_ROOT / "data_platform" / "transform"

dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
)
# En dev genera target/manifest.json on-the-fly; en CI/Docker el manifest se
# pre-genera en el build (ver Dockerfile.dagster y ci.yml).
dbt_project.prepare_if_dev()
```

- [ ] **Step 2: Generar el manifest localmente para validar el módulo**

Run:
```bash
cd /Users/varbelaiz/Code/Universidad/Software/ingenieria-software-dagster-dbt
uv run --group data dbt deps --project-dir data_platform/transform --profiles-dir data_platform/transform
uv run --group data dbt parse --project-dir data_platform/transform --profiles-dir data_platform/transform
```
Expected: crea `data_platform/transform/target/manifest.json` (exit 0).

- [ ] **Step 3: Añadir generación de manifest al `Dockerfile.dagster`**

Tras la línea `COPY data_platform/ ./data_platform/`, agregar:

```dockerfile
# Generar el manifest de dbt en build para que @dbt_assets cargue sin DB en runtime.
RUN dbt deps --project-dir data_platform/transform --profiles-dir data_platform/transform \
 && dbt parse --project-dir data_platform/transform --profiles-dir data_platform/transform
```

- [ ] **Step 4: Añadir paso de manifest al job `dagster-validate` de CI**

En `.github/workflows/ci.yml`, dentro del job `dagster-validate`, antes del paso "Validate Dagster Definitions load", insertar:

```yaml
      - name: Install dbt packages
        run: uv run --group data dbt deps --project-dir data_platform/transform --profiles-dir data_platform/transform

      - name: Generate dbt manifest for dagster-dbt
        run: uv run --group data dbt parse --project-dir data_platform/transform --profiles-dir data_platform/transform
```

- [ ] **Step 5: Commit**

```bash
git add data_platform/orchestration/dbt_project.py Dockerfile.dagster .github/workflows/ci.yml
git commit -m "feat(orchestration): add DbtProject and manifest generation for dagster-dbt"
```

---

### Task 2: `DagsterDbtTranslator` (mapeo source -> bronze)

**Files:**
- Create: `data_platform/orchestration/assets/transform.py` (parcial: solo el translator)
- Test: `tests/test_dbt_assets.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_dbt_assets.py
from dagster import AssetKey

from data_platform.orchestration.assets.transform import BronzeSourceTranslator


def test_source_maps_to_bronze_asset_key() -> None:
    translator = BronzeSourceTranslator()
    props = {"resource_type": "source", "name": "produccion_raw", "source_name": "bronze"}
    assert translator.get_asset_key(props) == AssetKey(["bronze_produccion_raw"])


def test_model_keeps_default_asset_key() -> None:
    translator = BronzeSourceTranslator()
    props = {
        "resource_type": "model",
        "name": "stg_produccion",
        "unique_id": "model.ingenieria_software.stg_produccion",
        "fqn": ["ingenieria_software", "silver", "stg_produccion"],
    }
    assert translator.get_asset_key(props) == AssetKey(["stg_produccion"])
```

- [ ] **Step 2: Correr el test para verque falla**

Run: `uv run --group data pytest tests/test_dbt_assets.py -v`
Expected: FAIL con ImportError (`BronzeSourceTranslator` no existe).

- [ ] **Step 3: Implementar el translator**

```python
# data_platform/orchestration/assets/transform.py
"""Assets dbt (silver/gold) integrados como assets de Dagster."""

from collections.abc import Mapping
from typing import Any

from dagster import AssetKey
from dagster_dbt import DagsterDbtTranslator


class BronzeSourceTranslator(DagsterDbtTranslator):
    """Mapea las sources bronze de dbt a las claves de los assets bronze de Dagster."""

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        if dbt_resource_props["resource_type"] == "source":
            return AssetKey([f"bronze_{dbt_resource_props['name']}"])
        return super().get_asset_key(dbt_resource_props)
```

- [ ] **Step 4: Correr el test para verque pasa**

Run: `uv run --group data pytest tests/test_dbt_assets.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add data_platform/orchestration/assets/transform.py tests/test_dbt_assets.py
git commit -m "feat(orchestration): map dbt bronze sources to bronze asset keys"
```

---

### Task 3: Helper de args por partición (reprocess_period)

**Files:**
- Modify: `data_platform/orchestration/assets/transform.py`
- Test: `tests/test_dbt_assets.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# añadir a tests/test_dbt_assets.py
from data_platform.orchestration.assets.transform import build_dbt_build_args


def test_build_args_without_partition() -> None:
    assert build_dbt_build_args(None) == ["build"]


def test_build_args_with_partition_injects_reprocess_period() -> None:
    args = build_dbt_build_args("2026-05-01")
    assert args[:1] == ["build"]
    assert "--vars" in args
    vars_value = args[args.index("--vars") + 1]
    assert vars_value == '{"reprocess_period": "2026-05-01"}'
```

- [ ] **Step 2: Correr el test para verque falla**

Run: `uv run --group data pytest tests/test_dbt_assets.py::test_build_args_with_partition_injects_reprocess_period -v`
Expected: FAIL (`build_dbt_build_args` no existe).

- [ ] **Step 3: Implementar el helper**

```python
# añadir a data_platform/orchestration/assets/transform.py
import json


def build_dbt_build_args(partition_key: str | None) -> list[str]:
    """Construye los args de `dbt build`, inyectando reprocess_period si hay partición."""
    args = ["build"]
    if partition_key is not None:
        args += ["--vars", json.dumps({"reprocess_period": partition_key})]
    return args
```

- [ ] **Step 4: Correr el test para verque pasa**

Run: `uv run --group data pytest tests/test_dbt_assets.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add data_platform/orchestration/assets/transform.py tests/test_dbt_assets.py
git commit -m "feat(orchestration): build dbt args with partition-driven reprocess_period"
```

---

### Task 4: La función `@dbt_assets` (freshness + build)

**Files:**
- Modify: `data_platform/orchestration/assets/transform.py`

- [ ] **Step 1: Añadir la función `@dbt_assets`**

```python
# añadir a data_platform/orchestration/assets/transform.py
from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from data_platform.orchestration.assets.bronze import bronze_monthly_partitions
from data_platform.orchestration.dbt_project import dbt_project

_translator = BronzeSourceTranslator()


@dbt_assets(
    manifest=dbt_project.manifest_path,
    partitions_def=bronze_monthly_partitions,
    dagster_dbt_translator=_translator,
)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """Materializa silver/gold: corre freshness (fail-fast) y luego dbt build."""
    # Fuentes rancias cortan la promoción antes de transformar.
    dbt.cli(["source", "freshness"], raise_on_error=True).wait()

    partition_key = context.partition_key if context.has_partition_key else None
    yield from dbt.cli(
        build_dbt_build_args(partition_key), context=context
    ).stream()
```

- [ ] **Step 2: Validar import (requiere manifest del Step 2 de Task 1)**

Run: `uv run --group data python -c "from data_platform.orchestration.assets.transform import dbt_models; print('ok', [k.to_user_string() for k in dbt_models.keys][:5])"`
Expected: imprime `ok` y una lista de claves de assets dbt (ej. `stg_produccion`, `stg_pozos`, `dim_pozo`, ...).

- [ ] **Step 3: Commit**

```bash
git add data_platform/orchestration/assets/transform.py
git commit -m "feat(orchestration): add @dbt_assets running freshness then partitioned build"
```

---

### Task 5: Asset job + limpieza de `jobs.py`

**Files:**
- Modify: `data_platform/orchestration/jobs.py`

- [ ] **Step 1: Reescribir `jobs.py` conservando solo hook + alerta + el asset job**

Reemplazar TODO el contenido de `data_platform/orchestration/jobs.py` por:

```python
"""Asset job y hook de alerta de calidad para la plataforma de datos."""

import json
import os
from urllib import error, request

from dagster import (
    AssetSelection,
    HookContext,
    define_asset_job,
    failure_hook,
)
from dagster._core.errors import DagsterInvalidPropertyError

from data_platform.orchestration.assets.bronze import bronze_monthly_partitions

ALERT_WEBHOOK_ENV = "DATA_QUALITY_ALERT_WEBHOOK_URL"


def _safe_context_value(context: HookContext, attribute: str, default: str) -> str:
    """Lee atributos del contexto de forma defensiva (runtime y tests)."""
    try:
        value = getattr(context, attribute)
    except (AttributeError, DagsterInvalidPropertyError):
        return default
    return default if value is None else str(value)


def _send_data_quality_webhook(
    context: HookContext, payload: dict[str, str], webhook_url: str
) -> None:
    """Envía la alerta a un webhook en runtime del job."""
    if not webhook_url.startswith("https://"):
        raise ValueError(f"Webhook URL must start with 'https://'; got: {webhook_url!r}")
    webhook_request = request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(webhook_request, timeout=5):
            context.log.info("Forwarded data quality alert to configured webhook.")
    except error.URLError as exc:
        context.log.warning("Failed to deliver data quality webhook alert: %s", exc)


def emit_data_quality_alert(
    context: HookContext, *, error_message: str, webhook_url: str | None = None
) -> dict[str, str]:
    """Loguea una alerta estructurada y opcionalmente la reenvía a un webhook."""
    op_name = "unknown"
    try:
        op_def = context.op
    except (AttributeError, DagsterInvalidPropertyError):
        op_def = None
    if op_def is not None:
        op_name = op_def.name
    payload = {
        "event": "data_quality_job_failed",
        "job_name": _safe_context_value(context, "job_name", "end_to_end_data_job"),
        "op_name": op_name,
        "run_id": _safe_context_value(context, "run_id", "unknown"),
        "error": error_message,
    }
    context.log.error("data_quality_alert=%s", json.dumps(payload, sort_keys=True))
    if webhook_url:
        _send_data_quality_webhook(context, payload, webhook_url)
    return payload


@failure_hook
def data_quality_failure_hook(context: HookContext) -> None:
    """Emite una alerta estructurada cuando el gate de calidad de dbt falla."""
    error_message = (
        str(context.op_exception) if context.op_exception else "Unknown failure"
    )
    emit_data_quality_alert(
        context, error_message=error_message, webhook_url=os.getenv(ALERT_WEBHOOK_ENV)
    )


end_to_end_data_job = define_asset_job(
    name="end_to_end_data_job",
    selection=AssetSelection.all(),
    partitions_def=bronze_monthly_partitions,
    hooks={data_quality_failure_hook},
)
```

- [ ] **Step 2: Verificar import limpio**

Run: `uv run --group data python -c "from data_platform.orchestration.jobs import end_to_end_data_job, data_quality_failure_hook; print('ok', end_to_end_data_job.name)"`
Expected: `ok end_to_end_data_job`.

- [ ] **Step 3: Commit**

```bash
git add data_platform/orchestration/jobs.py
git commit -m "refactor(orchestration): replace op job with asset job, keep alert hook"
```

---

### Task 6: Definiciones + borrar `dbt.py`

**Files:**
- Modify: `data_platform/orchestration/__init__.py`
- Delete: `data_platform/orchestration/dbt.py`

- [ ] **Step 1: Reescribir `__init__.py`**

Reemplazar TODO el contenido de `data_platform/orchestration/__init__.py` por:

```python
"""Dagster orchestration entrypoint for the data platform."""

from dagster import Definitions
from dagster_dbt import DbtCliResource

from data_platform.orchestration.assets.bronze import bronze_assets
from data_platform.orchestration.assets.transform import dbt_models
from data_platform.orchestration.datahub import build_datahub_sensor
from data_platform.orchestration.dbt_project import dbt_project
from data_platform.orchestration.jobs import end_to_end_data_job
from data_platform.orchestration.schedules import monthly_data_pipeline_schedule

datahub_sensor = build_datahub_sensor()

defs = Definitions(
    assets=[*bronze_assets, dbt_models],
    jobs=[end_to_end_data_job],
    schedules=[monthly_data_pipeline_schedule],
    sensors=[datahub_sensor] if datahub_sensor is not None else [],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
```

- [ ] **Step 2: Borrar el runner por subprocess**

Run: `git rm data_platform/orchestration/dbt.py`

- [ ] **Step 3: Validar que las Definitions cargan**

Run: `uv run --group data dagster definitions validate -m data_platform.orchestration`
Expected: exit 0, sin errores de carga.

- [ ] **Step 4: Commit**

```bash
git add data_platform/orchestration/__init__.py
git commit -m "feat(orchestration): wire dbt assets + DbtCliResource, drop subprocess runner"
```

---

### Task 7: Tests de orquestación (asset-based)

**Files:**
- Modify: `tests/test_orchestration_jobs.py`
- Test: `tests/test_dbt_assets.py` (smoke de Definitions)

- [ ] **Step 1: Reescribir `tests/test_orchestration_jobs.py`**

Reemplazar el contenido por tests del modelo asset-based:

```python
"""Tests del modelo asset-based de orquestación."""

from dagster import AssetKey

from data_platform.orchestration import defs
from data_platform.orchestration.jobs import (
    data_quality_failure_hook,
    end_to_end_data_job,
)


def test_definitions_expose_bronze_and_dbt_assets() -> None:
    keys = {k.to_user_string() for k in defs.get_asset_graph().all_asset_keys}
    assert "bronze_produccion_raw" in keys
    assert "bronze_pozos_raw" in keys
    assert "stg_produccion" in keys
    assert "fct_produccion" in keys


def test_dbt_models_depend_on_bronze_assets() -> None:
    graph = defs.get_asset_graph()
    deps = graph.get(AssetKey(["stg_produccion"])).parent_keys
    assert AssetKey(["bronze_produccion_raw"]) in deps


def test_asset_job_has_failure_hook() -> None:
    assert data_quality_failure_hook in end_to_end_data_job.hooks


def test_schedule_targets_asset_job() -> None:
    schedule = next(iter(defs.get_all_schedule_defs()))
    assert schedule.job.name == "end_to_end_data_job"
```

> Nota: estos tests requieren el manifest (Task 1, Step 2). El CI lo genera antes de pytest; localmente correr `dbt deps` + `dbt parse` una vez.

- [ ] **Step 2: Correr los tests**

Run: `uv run --group data pytest tests/test_orchestration_jobs.py tests/test_dbt_assets.py -v`
Expected: PASS (todos verdes).

- [ ] **Step 3: Verificar que no quedaron referencias muertas al código viejo**

Run: `grep -rn "run_end_to_end_dbt_build\|data_quality_job\|orchestration.dbt import\|from data_platform.orchestration.dbt " data_platform tests`
Expected: sin resultados.

- [ ] **Step 4: Commit**

```bash
git add tests/test_orchestration_jobs.py tests/test_dbt_assets.py
git commit -m "test(orchestration): cover asset-based dbt graph and wiring"
```

---

### Task 8: Documentación

**Files:**
- Modify: `docs/ADRs/11-orchestration-tool.md`
- Modify: `README.md`
- Modify: `docs/runbooks/data-engineer.md`

- [ ] **Step 1: Actualizar la "Confirmación" de ADR-11**

Reemplazar el párrafo de Confirmación por:

```markdown
### Confirmación

Confirmado en `data_platform/orchestration/`: los modelos dbt se exponen como assets de
Dagster vía `@dbt_assets` (`assets/transform.py`), conectados a los assets de bronze a
través de un `DagsterDbtTranslator`. El grafo muestra `bronze -> silver -> gold` granular
con asset checks por test, particiones mensuales con backfill por fecha
(`reprocess_period`), y `RetryPolicy` con backoff en la extracción.
```

- [ ] **Step 2: Actualizar el README**

En la sección de la plataforma de datos, reemplazar la mención al job op-based por:

```markdown
El pipeline corre como un grafo de assets de Dagster: los assets de bronze
(`bronze_produccion_raw`, `bronze_pozos_raw`) alimentan los modelos dbt de silver y gold,
expuestos como assets vía `dagster-dbt`. Para actualizar los workflows, materializar la
partición mensual desde la UI de Dagster (`http://localhost:3001`) o esperar al schedule
`monthly_data_pipeline_schedule`. El manifest de dbt se genera en el build de la imagen
(`Dockerfile.dagster`) y en CI antes de validar las Definitions.
```

- [ ] **Step 3: Actualizar el runbook de backfill**

En `docs/runbooks/data-engineer.md`, en los pasos de backfill, reemplazar "lanzar el op-job"
por: "materializar la partición del período en el grafo de assets (bronze + dbt) desde la
UI de Dagster; `dbt build` corre con `--vars reprocess_period=<período>` y los asset checks
validan calidad antes de promover a gold."

- [ ] **Step 4: Commit**

```bash
git add docs/ADRs/11-orchestration-tool.md README.md docs/runbooks/data-engineer.md
git commit -m "docs: update orchestration docs for dagster-dbt asset model"
```

---

### Task 9: Verificación E2E (stack en vivo + browser)

Verificación end-to-end como en la sesión: stack real + Playwright. NO basta pytest.

- [ ] **Step 1: Lint y tests**

Run:
```bash
uv run pre-commit run --all-files
uv run --group data pytest
```
Expected: pre-commit OK; pytest verde.

- [ ] **Step 2: Levantar el stack desde el worktree**

Run (desde el worktree; `.env.data` debe existir con el atajo de Metabase):
```bash
docker compose --env-file .env.data -f docker-compose.data.yml up -d --build
```
Expected: warehouse, dagster-webserver, dagster-daemon, metabase healthy. La imagen de Dagster ya trae el manifest (Task 1, Step 3).

- [ ] **Step 3: Validar Definitions y grafo granular (browser)**

- `uv run --group data dagster definitions validate -m data_platform.orchestration` → exit 0.
- Navegar a `http://localhost:3001/asset-groups` (Playwright) y capturar el lineage: debe mostrar `bronze_produccion_raw -> stg_produccion -> dim_*/fct_produccion -> quality_marks` como nodos separados, con asset checks.

- [ ] **Step 4: Materializar partición de fixtures (UI) -> verde**

- Sembrar fixtures: `uv run --group data python -m data_platform.ci.seed_bronze`.
- En la UI, materializar la partición `2026-05-01` del grafo (o `dagster asset materialize`).
- Verificar: run verde, `gold.quality_marks` 8/8 PASS, captura del run.

- [ ] **Step 5: Materializar partición real -> verde E2E**

- Materializar la partición real a través del orquestador (extrae ~490k filas; la base trae el fix del mapping).
- Verificar: run verde, grafo granular materializado, `gold.fct_produccion` poblado, 8/8 marcas PASS. Captura del run + del lineage.

- [ ] **Step 6: Metabase con datos reales (browser)**

- Re-provisionar si hace falta: `uv run --group data python -m data_platform.bi.provision`.
- Navegar a `http://localhost:3002/dashboard/2` y capturar el dashboard con datos reales.

- [ ] **Step 7: Push + PR**

```bash
git push -u origin feature/dagster-dbt-assets
gh pr create --base develop --head feature/dagster-dbt-assets \
  --title "feat(orchestration): expose dbt models as granular Dagster assets" \
  --body-file <(echo "Migración de dbt-subprocess a @dbt_assets. Ver docs/superpowers/specs/2026-06-15-dagster-dbt-asset-migration-design.md")
```

---

## Notas de verificación / riesgos

- **Manifest ausente**: si `dagster definitions validate` o pytest fallan con error de manifest, correr `dbt deps` + `dbt parse` primero. En la imagen Docker ya se genera en build.
- **Grafo desconectado**: si en el lineage las sources cuelgan sueltas, revisar que `BronzeSourceTranslator.get_asset_key` produzca exactamente `bronze_produccion_raw`/`bronze_pozos_raw` (Task 2).
- **`dbt source freshness` dentro de `@dbt_assets`**: si la invocación da problemas de stream/contexto, es el punto a ajustar (correrla sin `context` y con `raise_on_error=True`, como está en el plan).
- **Worktree vs. stack docker**: al levantar desde el worktree, el nombre de proyecto de compose cambia y los volúmenes son frescos; por eso se re-siembra (Step 4) antes de la verificación real.
