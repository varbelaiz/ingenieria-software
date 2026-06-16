# Diseño: migración de orquestación dbt a `@dbt_assets` (grafo granular)

Fecha: 2026-06-15
Branch: `feature/dagster-dbt-assets` (anidada sobre `fix/silver-source-column-mapping`, PR -> `develop`)

## Contexto y problema

Hoy el `end_to_end_data_job` de Dagster modela el pipeline con 3 ops:
`load_bronze_produccion_raw` -> `load_bronze_pozos_raw` -> `run_end_to_end_dbt_build`.
La transformación medallion (silver + gold + tests) ocurre **adentro** de ese último op,
que ejecuta `dbt build --select silver gold` como subprocess
(`data_platform/orchestration/dbt.py`). Para Dagster ese paso es una caja negra: el grafo
de assets solo muestra los dos assets de bronze; silver y gold no aparecen como nodos y su
lineage fino no es navegable desde Dagster.

Objetivo: que cada modelo dbt sea un asset de Dagster de primera clase, con un grafo
granular `bronze -> silver -> gold` y los tests dbt como asset checks.

## Decisiones tomadas (brainstorming)

1. **Migración completa**: reemplazar el op `run_end_to_end_dbt_build` por `@dbt_assets`.
2. **Particionar los assets dbt igual que bronze** (MonthlyPartitionsDefinition); la
   partición inyecta `--vars reprocess_period=<partition_key>`, traducción 1:1 del comando
   actual. Preserva el backfill por fecha.
3. **Retirar el `data_quality_job`** standalone: los tests dbt pasan a ser asset checks en
   el grafo. `dbt source freshness` se conserva como paso de calidad previo.
4. **Resolver el manifest con `dbt parse`** en el build de `Dockerfile.dagster` y en CI
   antes de `dagster definitions validate`.

## No-objetivos

- No cambiar los modelos dbt ni la lógica de transformación (ya corregidos en el fix base).
- No cambiar el warehouse, DataHub ni Metabase.
- No tocar los assets de bronze (siguen siendo assets Python nativos).

## Arquitectura

### Componentes nuevos

- `data_platform/orchestration/dbt_project.py`: define un `DbtProject` apuntando a
  `data_platform/transform`, con generación de manifest gestionada (`prepare_if_dev()` en
  desarrollo; manifest pre-generado en CI/Docker).
- `data_platform/orchestration/assets/transform.py`:
  - `@dbt_assets(manifest=..., partitions_def=bronze_monthly_partitions,
    dagster_dbt_translator=...)` con una función que invoca
    `dbt build` vía `DbtCliResource`, pasando `--vars {reprocess_period: partition_key}`
    cuando hay partición activa.
  - Un `DagsterDbtTranslator` que mapea las **sources** dbt `bronze.produccion_raw` y
    `bronze.pozos_raw` a los `AssetKey` de los assets bronze existentes, para conectar el
    grafo `bronze_produccion_raw -> stg_produccion -> ...`.

### Recurso

- `DbtCliResource(project_dir=...)` registrado en `Definitions.resources`.

### Conexión del grafo (punto clave)

Los `@dbt_assets` declaran dependencias sobre las **sources** dbt. El translator debe
producir, para cada source, el mismo `AssetKey` que exponen los assets de bronze
(`bronze_produccion_raw`, `bronze_pozos_raw`). Si las keys no coinciden, el grafo aparece
desconectado (sources colgando). Verificación explícita: en el lineage global,
`bronze_produccion_raw` debe ser upstream de `stg_produccion`.

### Particionado y reproceso

- `@dbt_assets` usa `partitions_def=bronze_monthly_partitions`.
- En el cuerpo, si hay `context.partition_key`, se construyen los `--vars` con
  `reprocess_period=<partition_key>` y se ejecuta `dbt build`. Replica exactamente
  `build_dbt_build_command(reprocess_period=...)` actual.
- Backfill = materializar la partición del rango en el grafo de assets (bronze + dbt).

### Calidad y alerta (se preservan)

- `dbt build` sigue cortando downstream ante un test `error` (gold queda sin materializar);
  ahora visible como **asset checks en rojo** sobre el modelo afectado.
- `store_failures: true` y la vista `quality_marks` quedan intactos (no se tocan los
  modelos).
- La **alerta** (`data_quality_failure_hook`) se mantiene asociada al asset job: si el run
  falla por checks `error`, dispara el log estructurado + webhook opcional.
- `dbt source freshness` se ejecuta **dentro de la misma función `@dbt_assets`, antes del
  `dbt build`**: la función corre `dbt.cli(["source", "freshness"], ...)` (fail-fast si hay
  fuentes rancias) y recién después hace `yield from dbt.cli(["build", ...]).stream()`. Así
  datos rancios cortan la materialización sin necesidad de un job separado.

### Job, schedule y Definitions

- Reemplazar `end_to_end_data_job` (op-based) por un **asset job**:
  `define_asset_job("end_to_end_data_job", selection=<bronze + dbt assets>,
  partitions_def=bronze_monthly_partitions, hooks={data_quality_failure_hook})`.
- `monthly_data_pipeline_schedule` apunta al nuevo asset job (mismo cron, misma lógica de
  última partición cerrada).
- `Definitions`: `assets = bronze_assets + [dbt_assets]`,
  `resources = {"dbt": DbtCliResource(...)}`, `jobs = [end_to_end_data_job]`,
  `schedules = [monthly_data_pipeline_schedule]`, `sensors` igual (el sensor de DataHub
  ahora captura también las materializaciones de los assets dbt).

### Manifest

`@dbt_assets` construye las definiciones desde `target/manifest.json` **al cargar las
Definitions**. Hay que garantizar el manifest antes de la carga en tres entornos:

- **Local/dev**: `DbtProject(...).prepare_if_dev()` genera el manifest on-the-fly.
- **CI** (`dagster-validate`): paso `dbt parse` (o `dagster-dbt project prepare`) antes de
  `dagster definitions validate -m data_platform.orchestration`.
- **Docker** (`Dockerfile.dagster`): correr `dbt deps` + `dbt parse` en el build para dejar
  `target/manifest.json` en la imagen, de modo que el webserver/daemon carguen sin generar
  manifest en runtime.

## Qué se elimina

- Op `run_end_to_end_dbt_build` y el `end_to_end_data_job` op-based (`jobs.py`).
- `data_quality_job` y sus ops (`run_dbt_quality_build`, `run_dbt_quality_source_freshness`).
- `data_platform/orchestration/dbt.py` (runner por subprocess) se retira por completo: el
  build y el `source freshness` ahora corren vía `DbtCliResource` dentro de `@dbt_assets`.
- Se mantienen: `data_quality_failure_hook`, `emit_data_quality_alert`, los assets bronze,
  `schedules.py` (re-apuntado), el sensor de DataHub.

## Testing

- `tests/test_orchestration_jobs.py` se reescribe: hoy valida el job op-based.
  - Nuevos tests: las `Definitions` cargan con los dbt assets (requiere manifest de test);
    el grafo conecta `bronze_*` -> dbt assets (assert sobre dependencias / asset keys);
    la partición propaga `reprocess_period` al comando dbt (test del builder de args);
    el `data_quality_failure_hook` sigue registrado en el job.
- CI: `dagster-validate` debe pasar con el manifest pre-generado. `dbt-parse` y `dbt-test`
  no cambian (el proyecto dbt es el mismo).

## Docs a actualizar

- ADR-11 (orchestration): actualizar la sección "Confirmación" al modelo asset-based con
  `@dbt_assets`; mencionar el trade-off resuelto (grafo granular vs. subprocess opaco).
- README y `docs/runbooks/data-engineer.md`: el backfill ahora se dispara materializando la
  partición de los assets (bronze + dbt) en vez de lanzar el op-job.

## Riesgos

- **Manifest en carga de Definitions**: si falta, las Definitions no cargan y rompe CI y la
  imagen Docker. Mitigación: `prepare_if_dev` + paso explícito en CI/Docker (decisión b).
- **Mapeo de AssetKeys source<->bronze**: si no coinciden, el grafo queda desconectado.
  Mitigación: translator explícito + verificación de lineage.
- **Compat de versiones**: `dagster-dbt>=0.20` ya está en `pyproject`. Confirmar que la API
  `@dbt_assets`/`DbtProject`/`DbtCliResource` de la versión resuelta es compatible con
  dagster 1.8+ y dbt 1.8+; ajustar pin si hace falta.
- **Worktree vs. stack docker**: el stack corre atado al working tree principal. La
  verificación en vivo re-apunta el compose al worktree (volúmenes frescos + re-seed de
  fixtures).

## Plan de verificación

La verificación es **E2E sobre el stack en vivo + browser automation (Playwright)**, igual
que se viene haciendo en esta sesión: no alcanza con tests unitarios, hay que ver el
pipeline corriendo a través del orquestador y el resultado en las UIs.

1. `dbt parse` genera manifest; `dagster definitions validate -m data_platform.orchestration`
   carga sin error.
2. Levantar el stack desde el worktree; en la UI de Dagster (browser), el lineage global
   muestra `bronze_produccion_raw -> stg_produccion -> dim_*/fct_produccion -> quality_marks`
   como nodos separados, con asset checks por test (captura de pantalla).
3. Materializar una partición (fixtures) desde la UI -> run verde, gold poblado, 8 marcas de
   calidad PASS.
4. Materializar la partición real (~490k filas, gracias a la base con el fix) a través del
   orquestador -> run verde end-to-end con el grafo granular (captura del run + del lineage).
5. Dashboard de Metabase (browser) mostrando los datos reales sobre el gold reconstruido.
6. `uv run pytest` de los tests de orquestación nuevos en verde.
