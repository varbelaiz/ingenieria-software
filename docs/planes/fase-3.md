# Plan de PRs - Fase 3: ML Engineering para la API predictiva

Fecha de entrega: 2026-07-11

## Como usar este documento vivo

Este archivo es el punto de entrada para cualquier persona o agente que continue el
desarrollo de Fase 3. Antes de empezar un PR, leer:

1. `AGENTS.md`
2. `README.md`
3. `docs/planes/fase-3.md`
4. Los ADRs asociados al PR en curso
5. Los tests existentes que toquen la misma superficie

Cada PR debe actualizar esta seccion antes de cerrarse:

| Campo | Valor |
|-------|-------|
| Ultima actualizacion | 2026-07-03 |
| Branch base esperada | cadena apilada PR 7 -> PR 8 -> PR 9 sobre `feature/model-registry-promotion` |
| Estado global | los 9 PRs de la fase abiertos; PR 7-9 (#50, #51, #52) apilados y listos para review |
| Siguiente PR recomendado | mergear la cadena en orden (#49 -> #50 -> #51 -> #52) hacia develop |
| Riesgo abierto principal | `pre-commit run --all-files` no pudo completar localmente en PR1 porque el entorno no pudo descargar hooks desde GitHub |

### Regla de handoff entre agentes

Al terminar un PR, agregar una nota breve en el bloque del PR con:

* estado: `pendiente`, `en progreso`, `listo para review`, `mergeado` o `bloqueado`
* branch real usada
* commits principales
* comandos de verificacion corridos
* archivos tocados mas importantes
* decisiones nuevas o desviaciones contra este plan
* siguiente PR desbloqueado

No borrar contexto historico util. Si una decision cambia, marcar la anterior como
reemplazada y explicar por que.

## Contexto y alcance

La Fase 3 agrega una capa de ML Engineering sobre la plataforma existente. El sistema ya
tiene API REST, monitoreo, warehouse Postgres, dbt, Dagster, DataHub y Metabase. La nueva
fase debe demostrar que la API de predicciones queda integrada con un proceso reproducible
de features, entrenamiento, tracking, registro de modelos, validacion, retraining y CI/CD.

Requisitos cubiertos por esta fase:

* Usuarios de API consumen predicciones por API REST.
* ML Engineers acceden a tracking de experimentos.
* Features usadas en inferencia quedan persistidas en un feature store.
* El entrenamiento es reproducible para un dia dado.
* El entrenamiento y despliegue de modelos corren de forma recurrente y automatica.
* Los pipelines de procesamiento se validan/despliegan por CI/CD.
* La arquitectura completa queda documentada en `README.md`.
* El video muestra integracion real: runs, metricas, llamadas API y trigger de retrain.

## Arquitectura objetivo

Flujo esperado:

```text
Data Warehouse / gold
        |
        v
Feature Store persistido
        |
        +------> Training dataset por as_of_date
        |              |
        |              v
        |        Training + Validation
        |              |
        |              v
        |        MLflow Tracking + Model Registry
        |              |
        |              v
        +------> Modelo promovido
                       |
                       v
API REST ------> carga modelo vigente + consulta features ------> prediccion

Dagster orquesta materializacion de features, training, validacion y retrain.
GitHub Actions valida pipelines, tests, dbt/Dagster y smoke tests de ML.
```

## Stack propuesto

| Capa | Herramienta elegida | Alternativas a comparar en ADR | Motivo resumido |
|------|---------------------|--------------------------------|-----------------|
| Feature store | Postgres en esquema dedicado | Feast, parquet versionado | Reusa warehouse y dbt/Dagster; suficiente para el alcance local |
| Experiment tracking | MLflow Tracking | Weights & Biases, Neptune, CSV/JSON propio | Corre local, registra params/metrics/artifacts y es estandar academico/profesional |
| Model registry | MLflow Model Registry | Artefactos versionados en storage, tabla propia en Postgres | Integra tracking + modelos + stages sin inventar registry propio |
| Orquestacion ML | Dagster jobs/assets | GitHub Actions cron, Airflow | Ya esta en el repo y permite retrain por fecha con observabilidad |
| CI/CD pipelines | GitHub Actions | Deploy manual, Dagster Cloud, Jenkins | Ya esta configurado; permite validar sin servicio live en produccion |

## Estrategia de PRs

Se planifican **9 PRs**, divisible por 3 personas. La regla es que cada PR sea revisable
por separado y deje evidencia verificable. Evitar PRs gigantes que mezclen ADRs,
infraestructura, training, API y video.

### Branching

* Crear cada branch desde la dependencia inmediata real.
* Si el PR depende de otro aun no mergeado, crear branch apilada sobre esa branch.
* Si el PR padre ya fue mergeado, rebasear o recrear desde `develop` actualizado.
* Mantener el orden de merge indicado en la tabla.
* Antes de empezar: `git fetch` y verificar que `develop` este al dia con `origin/develop`.

### Distribucion sugerida para 3 personas

| Persona | PRs sugeridos | Foco |
|---------|---------------|------|
| A | PR 2, PR 5, PR 8 | feature store, dataset/training, CI/CD |
| B | PR 3, PR 6, PR 9 | MLflow, registry/promocion, documentacion/demo |
| C | PR 1, PR 4, PR 7 | foundation, API, retraining/orquestacion |

La asignacion es flexible, pero el total queda balanceado: 3 PRs por persona.

## Matriz de PRs

| PR | Branch | Owner sugerido | Depende de | Estado | Entrega principal |
|----|--------|----------------|------------|--------|-------------------|
| 1 | `feature/mlops-foundation` | C | `develop` | listo para review | estructura ML + ADRs iniciales + README arquitectura base |
| 2 | `feature/ml-feature-store` | A | PR 1 | listo para review | feature store persistido y materializacion |
| 3 | `feature/mlflow-tracking` | B | PR 1 | listo para review | MLflow local + tracking helpers |
| 4 | `feature/prediction-api-contract` | C | PR 3 | listo para review | contrato API de prediccion y tests base |
| 5 | `feature/training-pipeline` | A | PR 2 + PR 3 + PR 4 | listo para review | entrenamiento reproducible por `as_of_date` |
| 6 | `feature/model-registry-promotion` | B | PR 3 + PR 5 | listo para review | registro, validacion y promocion de modelos |
| 7 | `feature/retraining-orchestration` | C | PR 2 + PR 5 + PR 6 | pendiente | retrain manual/recurrente con Dagster |
| 8 | `feature/ml-pipeline-cicd` | A | PR 5 + PR 6 + PR 7 | pendiente | CI/CD de pipelines ML |
| 9 | `feature/phase3-docs-demo` | B | PR 1-8 | pendiente | README final, runbook y guion/evidencia de video |

---

## PR 1: `feature/mlops-foundation`

**Branch:** `feature/mlops-foundation` desde `develop` actualizado
**Owner sugerido:** C
**Descripcion:** Cimientos documentales y estructura minima para que los otros PRs puedan
trabajar en paralelo sin inventar carpetas ni nombres.

### Que implementar

1. Crear estructura base:
   * `ml/__init__.py`
   * `ml/features/__init__.py`
   * `ml/training/__init__.py`
   * `ml/registry/__init__.py`
   * `ml/inference/__init__.py`
   * `ml/config.py` si hace falta centralizar paths/env vars.

2. Actualizar `README.md` con una seccion inicial de arquitectura Fase 3:
   * API REST
   * feature store
   * training
   * validation
   * experiment tracking
   * model registry
   * retraining
   * CI/CD
   * nota explicita: no hay servicio live de produccion para la entrega.

3. Crear ADRs base como borradores completos:
   * `docs/ADRs/20-experiment-tracking.md`
   * `docs/ADRs/21-feature-store.md`
   * `docs/ADRs/22-model-registry.md`
   * `docs/ADRs/23-training-orchestration.md`
   * `docs/ADRs/24-ml-pipeline-cicd.md`

4. Agregar referencia desde `docs/index.md` si corresponde.

### ADRs de este PR

Los ADRs pueden quedar con decision preliminar, pero deben incluir comparacion real de
alternativas desde el primer PR. No crear ADRs vacios ni documentos que solo describan
"lo que hicimos".

Ver la seccion "Detalle de ADRs de Fase 3" para el contenido esperado.

### Verificacion

```bash
uv run pytest
uv run pre-commit run --all-files
```

Si `pre-commit` queda bloqueado por el entorno, correr al menos tests y linters sobre los
archivos tocados, y anotar el bloqueo en este plan.

### Handoff

* Estado: listo para review
* Branch real: `feature/mlops-foundation`
* Comandos corridos:
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; uv run pytest` -> 133 passed, 20 skipped
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run black --config .pre-commit/.black.toml --check ml tests/test_ml_config.py`
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run flake8 --config .pre-commit/.flake8 ml tests/test_ml_config.py`
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run pylint --rcfile .pre-commit/.pylintrc --persistent=n ml tests/test_ml_config.py`
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run mypy --config-file .pre-commit/mypy.ini ml tests/test_ml_config.py`
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; uv run pytest tests/test_ml_config.py`
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PRE_COMMIT_HOME='.pre-commit-cache'; $env:GIT_CONFIG_COUNT='1'; $env:GIT_CONFIG_KEY_0='safe.directory'; $env:GIT_CONFIG_VALUE_0='C:/Users/tomas/OneDrive/Documents/GitHub/ingenieria-software'; uv run pre-commit run --all-files` -> bloqueado al descargar `https://github.com/psf/black/`
* Archivos clave:
  * `.gitignore`
  * `ml/config.py`
  * `tests/test_ml_config.py`
  * `docs/ADRs/20-experiment-tracking.md`
  * `docs/ADRs/21-feature-store.md`
  * `docs/ADRs/22-model-registry.md`
  * `docs/ADRs/23-training-orchestration.md`
  * `docs/ADRs/24-ml-pipeline-cicd.md`
  * `docs/planes/fase-3.md`
  * `README.md`
  * `docs/index.md`
* Siguiente PR desbloqueado: PR 2, PR 3 y PR 4

---

## PR 2: `feature/ml-feature-store`

**Branch:** `feature/ml-feature-store` desde PR 1 o `develop` si PR 1 ya fue mergeado
**Owner sugerido:** A
**Descripcion:** Persistir features de inferencia/entrenamiento en Postgres, reusando el
warehouse y los modelos gold existentes.

### Que implementar

1. Definir un esquema o convencion para features:
   * recomendado: esquema `ml_features` o modelos dbt bajo `data_platform/transform/models/ml_features/`.
   * grano sugerido: `pozo_id` o identificador de pozo + `as_of_date`.
   * no usar datos futuros respecto de `as_of_date`.

2. Crear features iniciales para prediccion:
   * produccion historica reciente por pozo
   * medias/ventanas moviles simples
   * tendencia simple
   * dias/meses con produccion disponible
   * atributos estables del pozo desde gold/silver si aportan valor.

3. Crear codigo de acceso:
   * `ml/features/store.py`
   * funciones tipadas para leer features por pozo y fecha.
   * errores claros cuando faltan features.

4. Integrar materializacion en Dagster o dbt:
   * asset/job para materializar features por fecha.
   * idempotencia al re-materializar la misma fecha.

5. Tests:
   * lectura de features por fecha.
   * idempotencia.
   * ausencia de leakage temporal.
   * error controlado si no hay features.

### ADR asociado

Completar `docs/ADRs/21-feature-store.md`.

Decision recomendada: **Postgres como feature store persistido**.

Alternativas obligatorias:

* Postgres/dbt/Dagster sobre el warehouse existente.
* Feast.
* Parquet versionado o archivos locales.

### Verificacion

```bash
uv run --group data python -m data_platform.ci.seed_bronze
uv run --group data dbt build --select silver gold --project-dir data_platform/transform --profiles-dir data_platform/transform
uv run --group data pytest tests/test_feature_store.py
```

Si se agregan modelos dbt de features, sumar:

```bash
uv run --group data dbt build --select ml_features --project-dir data_platform/transform --profiles-dir data_platform/transform
```

### Handoff

* Estado: listo para review
* Branch real: `feature/ml-feature-store`
* Comandos corridos:
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; uv run pytest tests/test_feature_store.py` -> RED inicial: `ModuleNotFoundError: No module named 'ml.features.store'`
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; uv run pytest tests/test_feature_store.py` -> RED dbt: 2 failures por `FileNotFoundError` de `data_platform/transform/models/ml_features/well_monthly_features.sql`
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; uv run pytest tests/test_feature_store.py` -> 7 passed
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run black --config .pre-commit/.black.toml --check ml/features/store.py tests/test_feature_store.py` -> passed
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run flake8 --config .pre-commit/.flake8 ml/features/store.py tests/test_feature_store.py` -> passed
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run pylint --rcfile .pre-commit/.pylintrc --persistent=n ml/features/store.py tests/test_feature_store.py` -> 10.00/10
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run mypy --config-file .pre-commit/mypy.ini ml/features/store.py tests/test_feature_store.py` -> success
  * `$env:UV_CACHE_DIR='.uv-cache'; uv run --group data dbt parse --project-dir data_platform/transform --profiles-dir data_platform/transform` -> passed con warning existente de config path `models.ingenieria_software.bronze` sin recursos
* Tablas/modelos creados:
  * `data_platform/transform/models/ml_features/well_monthly_features.sql`
  * `data_platform/transform/models/ml_features/_ml_features__models.yml`
* Funcion publica principal: `FeatureStore.get_features()` con `PostgresFeatureRepository.lookup_features()`
* Decisiones/desviaciones:
  * Materializacion PR2 via dbt incremental; Dagster hook queda para PR7/orquestacion.
  * No se ejecuto `dbt build` contra warehouse live para evitar mutaciones fuera del alcance de los tests locales.
* Siguiente PR desbloqueado: PR 5 cuando PR 3 tambien este integrado

---

## PR 3: `feature/mlflow-tracking`

**Branch:** `feature/mlflow-tracking` desde PR 1 o `develop` si PR 1 ya fue mergeado
**Owner sugerido:** B
**Descripcion:** Levantar plataforma de tracking de experimentos y helpers para registrar
runs, parametros, metricas y artefactos.

### Que implementar

1. Agregar MLflow al stack local:
   * dependencia en `pyproject.toml`, probablemente dentro de grupo `data` o nuevo grupo `ml`.
   * servicio `mlflow` en compose existente o compose dedicado.
   * artifact store local versionado como volumen, no archivos sueltos sin documentar.

2. Crear helpers:
   * `ml/training/tracking.py`
   * configurar tracking URI desde env var.
   * funcion para iniciar run con tags estandar:
     * `as_of_date`
     * `git_sha`
     * `dataset_start`
     * `dataset_end`
     * `feature_view`
     * `model_type`

3. Crear smoke script opcional:
   * `ml/training/smoke_tracking.py` o comando equivalente.
   * registra un run de prueba con metricas dummy.

4. Documentar acceso:
   * URL local de MLflow.
   * comandos para levantarlo.
   * como ver runs y metricas.

### ADR asociado

Completar `docs/ADRs/20-experiment-tracking.md`.

Decision recomendada: **MLflow Tracking**.

Alternativas obligatorias:

* MLflow.
* Weights & Biases.
* Neptune.
* tracking casero con CSV/JSON solo como anti-opcion.

### Verificacion

```bash
uv run pytest tests/test_mlflow_tracking.py
```

Y manual/demo:

```bash
docker compose -f docker-compose.ml.yml up -d
uv run --group ml python -m ml.training.smoke_tracking
```

Adaptar nombres si se decide no crear grupo `ml` o compose separado.

### Handoff

* Estado: listo para review
* Branch real: `feature/mlflow-tracking`
* Comandos corridos:
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; uv run --group ml pytest tests/test_mlflow_tracking.py` -> 2 passed, 1 error por `PermissionError` creando `D:\WORKSPACE\SYSTEM\temp\pytest-of-tomas`
  * `$env:UV_CACHE_DIR='.uv-cache'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; $env:TMP='.tmp'; $env:TEMP='.tmp'; uv run --group ml pytest tests/test_mlflow_tracking.py` -> 3 passed
* URL local MLflow: `http://localhost:5000` via `docker compose -f docker-compose.ml.yml up -d`
* Funcion publica principal: `start_tracked_run()` y `run_smoke_tracking()`
* Archivos clave:
  * `pyproject.toml`
  * `uv.lock`
  * `docker-compose.ml.yml`
  * `.env.ml.example`
  * `ml/training/tracking.py`
  * `ml/training/smoke_tracking.py`
  * `tests/test_mlflow_tracking.py`
  * `docs/ADRs/20-experiment-tracking.md`
* Decisiones/desviaciones:
  * Tests usan `TMP/TEMP=.tmp` por permisos locales sobre `D:\WORKSPACE\SYSTEM\temp`.
  * No se implementa training real en PR3; queda para PR5.
* Siguiente PR desbloqueado: PR 5 y PR 6

---

## PR 4: `feature/prediction-api-contract`

**Branch:** `feature/prediction-api-contract` desde PR 1 o `develop` si PR 1 ya fue mergeado
**Owner sugerido:** C
**Descripcion:** Definir el contrato REST de predicciones ML sin esperar a que el modelo
final exista. El objetivo es que API, tests y demo tengan una superficie estable.

### Que implementar

1. Crear o extender router:
   * opcion recomendada: `app/predictions/routes.py`.
   * endpoint sugerido: `POST /predictions`.
   * endpoint de diagnostico sugerido: `GET /models/current`.

2. Modelos de request/response:
   * pozo o well id.
   * `as_of_date`.
   * horizonte de prediccion si aplica.
   * prediccion numerica.
   * metadata del modelo: version/run id/stage.
   * metadata de features: `feature_as_of_date`.

3. Implementar un adapter temporal:
   * `ml/inference/service.py`.
   * mientras PR 6 no exista, puede devolver prediccion baseline controlada.
   * dejar TODO claro o feature flag para conectar registry real despues.

4. Recomendacion no bloqueante para evaluar durante el diseño:
   * definir como la API adoptaria un modelo nuevo cuando PR 6 promueva una version en
     el registry.
   * comparar al menos consulta dinamica del modelo vigente, cache con refresh y reinicio
     controlado del servicio.
   * no es necesario implementar el mecanismo definitivo en este PR; alcanza con evitar
     que el contrato o el adapter temporal impidan incorporarlo despues.

5. Tests con `tests.TEST_API_KEY`:
   * request exitoso.
   * auth requerida.
   * pozo inexistente o features faltantes.
   * formato de respuesta estable.

### ADR asociado

No requiere ADR propio salvo que cambie la estrategia de API. Si se decide modificar
fuertemente el contrato de Fase 1, actualizar o crear ADR especifico.

### Verificacion

```bash
uv run pytest tests/test_predictions.py
uv run pytest tests/test_middleware.py
```

### Handoff

* Estado: listo para review
* Branch real: `feature/prediction-api-contract`, con PR 3 mergeado
* Comandos corridos:
  * `.venv/bin/pytest tests/test_predictions.py tests/test_middleware.py tests/test_forecast.py -q`
    -> 19 passed
  * `.venv/bin/python -m black --check ...`, `flake8` y `mypy` sobre los archivos
    tocados -> sin errores
  * `.venv/bin/pytest -q` -> bloqueado durante collection porque el entorno no tiene
    instalados `mlflow` ni el ejecutable `dbt`; `uv` tampoco esta disponible en `PATH`
* Endpoints agregados:
  * `POST /api/v1/predictions`
  * `GET /api/v1/models/current`
* Contrato request/response:
  * request: `well_id`, `as_of_date`, `horizon_days` (1-365)
  * response: prediccion numerica, metadata estable de modelo y `feature_as_of_date`
  * adapter actual: `BaselinePredictionService`, reemplazable por la implementacion de
    registry de PR 6 mediante el protocolo `PredictionService`
* Archivos clave:
  * `app/predictions/routes.py`
  * `ml/inference/service.py`
  * `tests/test_predictions.py`
* Siguiente PR desbloqueado: PR 5 cuando PR 2, PR 3 y PR 4 esten integrados

---

## PR 5: `feature/training-pipeline`

**Branch:** `feature/training-pipeline` desde PR 2 + PR 3 integrados o apilada sobre ambos
**Owner sugerido:** A
**Descripcion:** Entrenamiento reproducible para un `as_of_date`, leyendo desde feature
store y registrando runs reales en MLflow.

### Que implementar

1. Dataset builder:
   * `ml/training/dataset.py`.
   * input: `as_of_date`.
   * output: features `X`, target `y`, metadata de ventana temporal.
   * garantizar que no haya leakage temporal.

2. Modelo baseline:
   * usar un modelo simple y defendible.
   * recomendado: regresion lineal/sklearn o baseline estadistico si se quiere minimizar
     dependencias.
   * mantener la API de entrenamiento extensible, pero no sobredisenar.

3. Training entrypoint:
   * `ml/training/train.py`.
   * CLI: `--as-of-date YYYY-MM-DD`.
   * registra params/metrics/artifacts en MLflow.
   * produce metricas comparables entre runs: MAE, RMSE y cantidad de filas.

4. Tests:
   * dataset reproducible para la misma fecha.
   * metricas generadas.
   * run de MLflow mockeado o smoke local.

### ADR relacionado

Este PR consume ADR-20 y ADR-21. Si se elige una familia de modelo no trivial, agregar
una seccion en README o un ADR nuevo solo si la decision es clave para la fase.

### Verificacion

```bash
uv run --group data python -m data_platform.ci.seed_bronze
uv run --group data dbt build --select silver gold --project-dir data_platform/transform --profiles-dir data_platform/transform
uv run --group ml python -m ml.training.train --as-of-date 2024-12-31
uv run --group ml pytest tests/test_training_dataset.py tests/test_training_pipeline.py
```

### Handoff

* Estado: listo para review
* Branch real: `feature/training-pipeline`, apilada sobre PR 4 y con PR 2 mergeado
* Comandos corridos:
  * `.venv/bin/pytest tests/test_training_dataset.py tests/test_training_pipeline.py tests/test_feature_store.py -q`
    -> 12 passed
  * Black, flake8 y mypy sobre dataset, training, feature store y tests -> sin errores
  * smoke real contra Postgres/MLflow pendiente porque el entorno local no tiene `uv`,
    `dbt` ni `mlflow` instalados
* Metricas registradas:
  * `mae`, `rmse`, `rows`
  * parametros: `model_type=linear_regression`, `feature_count=1`
  * artefacto: `model/model.json`
* Run IDs de ejemplo: cubierto con `run-123` en el test de tracking; run local real
  pendiente del stack de datos/MLflow
* Decisiones:
  * target: `gas_production_current` del siguiente snapshot mensual conocido
  * no se agrega scikit-learn: OLS univariado determinista y portable es suficiente
    para el baseline y evita una dependencia adicional
* Siguiente PR desbloqueado: PR 6 y PR 7

---

## PR 6: `feature/model-registry-promotion`

**Branch:** `feature/model-registry-promotion` desde PR 3 + PR 5 integrados
**Owner sugerido:** B
**Descripcion:** Registrar modelos entrenados, validar criterios minimos y conectar la
API al modelo promovido.

### Que implementar

1. Registry helpers:
   * `ml/registry/client.py`.
   * registrar modelo desde run.
   * consultar modelo actual.
   * resolver artifact/model URI.

2. Politica de promocion:
   * `ml/registry/promotion.py`.
   * criterio minimo: metrica bajo threshold o mejor que modelo actual.
   * registrar estado: promoted/rejected/staging.
   * no promover si faltan metricas o validacion.

3. Integracion con inferencia:
   * `ml/inference/service.py` carga modelo vigente.
   * endpoint `GET /models/current` devuelve version/run id/metrica/stage.
   * endpoint `POST /predictions` usa feature store + modelo vigente.

4. Tests:
   * modelo promovido se resuelve correctamente.
   * modelo rechazado no reemplaza vigente.
   * API responde con metadata del modelo.
   * error claro si no hay modelo promovido.

### ADR asociado

Completar `docs/ADRs/22-model-registry.md`.

Decision recomendada: **MLflow Model Registry**.

Alternativas obligatorias:

* MLflow Model Registry.
* artefactos versionados en filesystem/storage + metadata en JSON.
* tabla propia en Postgres.

### Verificacion

```bash
uv run --group ml pytest tests/test_model_registry.py tests/test_model_promotion.py tests/test_predictions.py
```

Demo manual:

```bash
uv run --group ml python -m ml.training.train --as-of-date 2024-12-31
uv run --group ml python -m ml.registry.promote --run-id <RUN_ID>
uv run uvicorn app.main:app --reload
```

### Handoff

* Estado: listo para review
* Branch real: `feature/model-registry-promotion`, apilada sobre PR 5
* Comandos corridos:
  * `.venv/bin/pytest tests/test_model_registry.py tests/test_model_promotion.py tests/test_registry_inference.py tests/test_predictions.py tests/test_training_dataset.py tests/test_training_pipeline.py tests/test_feature_store.py -q`
    mas middleware y forecast -> 40 passed
  * Black, flake8, mypy y pylint sobre registry, inference, API y tests -> sin errores;
    pylint 10.00/10
  * demo real contra MLflow/Postgres pendiente por dependencias ausentes en el entorno
* Modelo/version promovido de ejemplo: version `4`, run `run-4`, alias `champion` en
  tests; politica validada para promoted/rejected/missing MAE
* Endpoint verificado:
  * `POST /api/v1/predictions` usa features point-in-time y el champion
  * `GET /api/v1/models/current` devuelve nombre, version, run ID, alias y metricas
  * ausencia de champion devuelve `503`
* Decisiones:
  * aliases `candidate`/`champion`; no se usan stages deprecados
  * backend por defecto: registry; `ML_INFERENCE_BACKEND=baseline` conserva fallback
    explicito para desarrollo
  * horizontes mayores a 30 dias aplican el modelo recursivamente por mes
* Siguiente PR desbloqueado: PR 7

---

## PR 7: `feature/retraining-orchestration`

**Branch:** `feature/retraining-orchestration` desde PR 2 + PR 5 + PR 6 integrados
**Owner sugerido:** C
**Descripcion:** Orquestar materializacion de features, training, validacion y promocion
con Dagster, permitiendo retrain manual para un dia dado y schedule recurrente.

### Que implementar

1. Dagster job/assets:
   * `data_platform/orchestration/assets/ml.py` o modulo equivalente.
   * asset de feature materialization.
   * op/asset de training.
   * op/asset de validation/promotion.

2. Job parametrizable:
   * `train_model_job`.
   * config con `as_of_date`.
   * re-ejecutable para el mismo dia.

3. Schedule:
   * schedule recurrente para retraining.
   * documentar frecuencia elegida.

4. Trigger manual:
   * desde UI de Dagster o CLI.
   * dejar comando exacto en runbook.

5. Tests:
   * definitions cargan.
   * job existe.
   * config valida.
   * al menos un smoke test del flujo con fixtures.

### ADR asociado

Completar `docs/ADRs/23-training-orchestration.md`.

Decision recomendada: **Dagster para retraining ML**.

Alternativas obligatorias:

* Dagster.
* GitHub Actions scheduled workflow.
* Airflow.

### Verificacion

```bash
uv run --group data dagster definitions validate -m data_platform.orchestration
uv run --group ml pytest tests/test_ml_orchestration.py
```

Demo manual:

```bash
docker compose --env-file .env.data -f docker-compose.data.yml up -d
# abrir Dagster y disparar train_model_job con as_of_date
```

### Handoff

* Estado: listo para review (#50)
* Branch real: `feature/retraining-orchestration` (apilada sobre `feature/model-registry-promotion`)
* Comandos corridos:
  * `uv run --group data --group ml dagster definitions validate -m data_platform.orchestration` -> OK
  * `uv run --group data --group ml pytest tests/test_ml_orchestration.py` -> 6 passed
  * `uv run --group data --group ml pytest tests/test_orchestration_jobs.py tests/test_dbt_assets.py` -> 8 passed
* Job/schedule creado: `train_model_job` + `ml_retraining_schedule` (mensual, dia 2 04:00 ART)
* Forma de trigger manual: materializar la particion mensual de `train_model_job` desde la UI de Dagster
* Archivos clave: `data_platform/orchestration/assets/ml.py`, `jobs.py`, `schedules.py`, `__init__.py`, `tests/test_ml_orchestration.py`
* Siguiente PR desbloqueado: PR 8 y PR 9

---

## PR 8: `feature/ml-pipeline-cicd`

**Branch:** `feature/ml-pipeline-cicd` desde PR 5 + PR 6 + PR 7 integrados
**Owner sugerido:** A
**Descripcion:** Validar automaticamente los pipelines de ML en CI/CD sin requerir un
servicio live de produccion.

### Que implementar

1. Extender `.github/workflows/ci.yml`:
   * instalar dependencias ML.
   * correr tests de feature store/training/registry.
   * validar Dagster definitions.
   * smoke test de training con dataset chico o fixtures.

2. Si hace falta, agregar workflow separado:
   * `.github/workflows/ml-pipeline.yml`.
   * mantenerlo chico y reproducible.

3. Asegurar que no dependa de secretos reales:
   * usar Postgres service container.
   * usar tracking URI local temporal.
   * artifact store temporal dentro del runner.

4. Documentar equivalentes locales:
   * comandos para correr los mismos checks fuera de GitHub.

5. Recomendacion no bloqueante para evaluar segun el alcance disponible:
   * complementar los checks de CI con una evidencia minima de CD, por ejemplo construir
     y versionar una imagen o artefacto del pipeline y ejecutar un smoke deployment.
   * no requiere publicar un servicio live en produccion; puede resolverse con un
     artefacto del workflow o un despliegue efimero y reproducible.
   * documentar la alternativa evaluada y el motivo si se decide no incorporarla.

### ADR asociado

Completar `docs/ADRs/24-ml-pipeline-cicd.md`.

Decision recomendada: **GitHub Actions como CI/CD de pipelines ML**.

Alternativas obligatorias:

* GitHub Actions.
* deploy/manual local.
* Dagster Cloud u otro scheduler gestionado.
* Jenkins/GitLab CI si quieren comparar generico.

### Verificacion

```bash
uv run pytest
uv run --group data dagster definitions validate -m data_platform.orchestration
uv run --group ml pytest tests/test_feature_store.py tests/test_training_pipeline.py tests/test_model_registry.py
```

Ademas, verificar el workflow en GitHub cuando se abra el PR.

### Handoff

* Estado: listo para review (#51)
* Branch real: `feature/ml-pipeline-cicd` (apilada sobre `feature/retraining-orchestration`)
* Comandos corridos:
  * `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` -> OK
  * smoke con warehouse en GitHub Actions; ruta feature store -> dataset -> training cubierta por `tests/test_ml_orchestration.py`
* Workflows modificados: `.github/workflows/ci.yml` (dbt-test construye `ml_features`; nuevo job `ml-pipeline-smoke`; `--cov=ml`)
* Checks esperados en PR: `dbt-test` (con data tests de `ml_features`), `ml-pipeline-smoke`, `dagster-validate`, `test`
* Siguiente PR desbloqueado: PR 9

---

## PR 9: `feature/phase3-docs-demo`

**Branch:** `feature/phase3-docs-demo` desde todos los PRs previos integrados
**Owner sugerido:** B
**Descripcion:** Cierre de documentacion, runbook de demo y guion del video de 5 a 10
minutos.

### Que implementar

1. Completar `README.md`:
   * arquitectura completa.
   * herramientas usadas.
   * comandos de quickstart.
   * como correr API + MLflow + Dagster + feature store.
   * como hacer retrain para un dia dado.

2. Crear runbook:
   * `docs/runbooks/ml-engineer.md`.
   * levantar stack.
   * materializar features.
   * entrenar modelo.
   * ver runs en MLflow.
   * promover o ver modelo vigente.
   * llamar API.
   * disparar retrain.

3. Crear guion/evidencia para video:
   * `docs/fase-3-video.md`.
   * seccion "que mostrar".
   * seccion "que decir".
   * comandos exactos.
   * capturas sugeridas: MLflow runs, Dagster job, API calls.

4. Revisar todos los ADRs:
   * confirmar que cada uno compara alternativas.
   * confirmar que no son solo descripcion del camino tomado.
   * agregar "Confirmacion" con archivos reales implementados.

### Verificacion

```bash
uv run pytest
uv run --group data dagster definitions validate -m data_platform.orchestration
uv run pre-commit run --all-files
```

Demo completa esperada:

```bash
docker compose --env-file .env.data -f docker-compose.data.yml up -d
docker compose -f docker-compose.ml.yml up -d
uv run --group data python -m data_platform.ci.seed_bronze
uv run --group data dbt build --select silver gold --project-dir data_platform/transform --profiles-dir data_platform/transform
uv run --group ml python -m ml.training.train --as-of-date 2024-12-31
uv run --group ml python -m ml.registry.promote --run-id <RUN_ID>
uv run uvicorn app.main:app --reload
```

Despues llamar API con `curl`, PowerShell o `httpx` usando `X-API-Key`.

### Handoff

* Estado: listo para review (#52)
* Branch real: `feature/phase3-docs-demo` (apilada sobre `feature/ml-pipeline-cicd`)
* Comandos corridos:
  * `uv run --group data --group ml dagster definitions validate -m data_platform.orchestration` -> OK
  * black / flake8 sobre los archivos tocados
* Evidencia lista para video: guion en `docs/fase-3-video.md` (feature store, 2 runs MLflow, promocion, API en 2 condiciones, retrain en Dagster)
* Archivos clave: `README.md` (seccion Fase 3), `docs/runbooks/ml-engineer.md`, `docs/fase-3-video.md`, ADR-23/ADR-24 (Confirmacion), `docs/index.md`
* Entrega final: Fase 3 completa; los 9 PRs de la fase abiertos/apilados apuntando a develop

---

## Detalle de ADRs de Fase 3

Todos los ADRs deben mantener el estilo existente:

* `status`
* `date`
* `decision-makers`
* contexto y problema
* impulsores de decision
* opciones consideradas
* resultado de decision
* consecuencias buenas y malas
* confirmacion con archivos reales

### ADR-20: Experiment tracking

**Archivo:** `docs/ADRs/20-experiment-tracking.md`

**Problema:** Los ML Engineers necesitan ver runs de entrenamiento, parametros, metricas
y artefactos para comparar experimentos y reproducir resultados.

**Drivers:**

* UI local para ver runs.
* Registro de parametros, metricas y artifacts.
* Bajo costo operativo.
* Integracion posible con registry.
* Buen encaje con demo de la materia.

**Opciones a comparar:**

* **MLflow Tracking:** local, open source, tracking + artifacts + registry.
* **Weights & Biases:** excelente UI gestionada, pero requiere servicio externo/cuenta.
* **Neptune:** fuerte para equipos ML, pero suma vendor externo.
* **CSV/JSON propio:** simple, pero pobre para comparacion y reproducibilidad.

**Decision recomendada:** MLflow Tracking.

**Confirmacion esperada:** compose/servicio MLflow, helpers en `ml/training/tracking.py`,
training registrando metricas reales, tests o smoke script.

### ADR-21: Feature store

**Archivo:** `docs/ADRs/21-feature-store.md`

**Problema:** Las features usadas por entrenamiento e inferencia deben persistirse y
consultarse de forma consistente para evitar skew entre training y serving.

**Drivers:**

* Persistencia.
* Reuso por training e inferencia.
* Reprocesamiento por fecha.
* No leakage temporal.
* Integracion con Postgres/dbt/Dagster ya existentes.

**Opciones a comparar:**

* **Postgres como feature store:** esquema/tablas persistidas, materializadas por dbt o
  Dagster.
* **Feast:** feature store dedicado, mas completo, pero agrega complejidad operativa.
* **Parquet versionado:** simple para batch, mas incomodo para API online.

**Decision recomendada:** Postgres como feature store persistido.

**Confirmacion esperada:** modelos/tablas de features, codigo `ml/features/store.py`,
tests de idempotencia y lookup por fecha.

### ADR-22: Model registry

**Archivo:** `docs/ADRs/22-model-registry.md`

**Problema:** La API necesita resolver un modelo vigente/promovido, y el equipo necesita
trazabilidad entre run, metricas, artefacto y version servida.

**Drivers:**

* Versionado de modelos.
* Relacion modelo-run-metricas.
* Promocion/rechazo.
* Integracion con API.
* Evitar inventar registry casero.

**Opciones a comparar:**

* **MLflow Model Registry:** integrado con tracking y artifacts.
* **Artefactos versionados + JSON:** simple, pero con poca trazabilidad y validacion.
* **Tabla propia en Postgres:** control total, pero alto riesgo de reinventar mal.

**Decision recomendada:** MLflow Model Registry.

**Confirmacion esperada:** helpers en `ml/registry/`, CLI o funcion de promocion, endpoint
`GET /models/current`, tests de modelo promovido/rechazado.

### ADR-23: Training orchestration

**Archivo:** `docs/ADRs/23-training-orchestration.md`

**Problema:** El entrenamiento debe repetirse para un dia dado y ejecutarse de manera
recurrente/automatica.

**Drivers:**

* Parametro `as_of_date`.
* Trigger manual demostrable.
* Schedule recurrente.
* Observabilidad de runs.
* Reuso de Dagster ya existente.

**Opciones a comparar:**

* **Dagster:** assets/jobs/schedules, UI local, ya presente en repo.
* **GitHub Actions cron:** simple para schedules, pobre para observabilidad de datos y
  trigger parametrico.
* **Airflow:** maduro, pero agrega stack paralelo innecesario.

**Decision recomendada:** Dagster.

**Confirmacion esperada:** `train_model_job`, schedule, config por `as_of_date`,
validacion de definitions y runbook de trigger manual.

### ADR-24: ML pipeline CI/CD

**Archivo:** `docs/ADRs/24-ml-pipeline-cicd.md`

**Problema:** Los pipelines de procesamiento/ML deben validarse y desplegarse mediante
CI/CD, aunque la entrega no tenga servicio live en produccion.

**Drivers:**

* Checks automaticos por PR.
* No depender de secretos reales.
* Validar dbt, Dagster, feature store, training y registry.
* Mantener consistencia con CI existente.

**Opciones a comparar:**

* **GitHub Actions:** ya usado por el repo, soporta service containers y jobs por PR.
* **Deploy manual/local:** simple, pero no cumple automatizacion.
* **Dagster Cloud u orquestador gestionado:** potente, pero excede alcance/costo.
* **Jenkins/GitLab CI:** validos, pero no estan integrados al repo actual.

**Decision recomendada:** GitHub Actions.

**Confirmacion esperada:** jobs CI para ML, smoke training, validate Dagster definitions,
tests de API/registry y documentacion de comandos locales equivalentes.

---

## Checklist de video final

El video debe durar entre 5 y 10 minutos. No mostrar solo slides: demostrar integracion
real del proceso ML con la API.

Orden recomendado:

1. Arquitectura completa en `README.md`.
2. Feature store persistido en Postgres.
3. MLflow con al menos dos runs y metricas distintas.
4. Modelo registrado/promovido.
5. API respondiendo predicciones con metadata del modelo.
6. Trigger manual de retrain en Dagster para un `as_of_date`.
7. Nuevo run en MLflow despues del retrain.
8. Cierre: valor agregado en reproducibilidad, trazabilidad y reduccion de skew.

Evidencia minima antes de grabar:

* Captura o demo de MLflow con multiples runs.
* Captura o demo de Dagster con job de retraining.
* Llamadas API con dos condiciones distintas.
* Comando de retrain para un dia dado.
* README y ADRs visibles.

## Comandos base de referencia

Estos comandos deben ajustarse si los PRs cambian nombres de grupos o compose files.

```bash
uv sync
uv sync --group data
uv run pytest
uv run pre-commit run --all-files
uv run --group data python -m data_platform.ci.seed_bronze
uv run --group data dbt build --select silver gold --project-dir data_platform/transform --profiles-dir data_platform/transform
uv run --group data dagster definitions validate -m data_platform.orchestration
docker compose --env-file .env.data -f docker-compose.data.yml up -d
```

Comandos esperados a incorporar cuando existan PRs ML:

```bash
uv sync --group ml
docker compose -f docker-compose.ml.yml up -d
uv run --group ml python -m ml.training.train --as-of-date 2024-12-31
uv run --group ml python -m ml.registry.promote --run-id <RUN_ID>
uv run uvicorn app.main:app --reload
```

## Anti-patrones a evitar

* ADRs sin alternativas reales.
* Feature store que solo existe en memoria durante training.
* API que recalcula features de una forma distinta al training.
* Training sin `as_of_date`.
* Runs sin metricas comparables.
* Modelo servido sin version/run id visible.
* Retrain que solo sea un comando manual sin schedule ni orquestacion.
* CI que solo corre tests de API y no valida pipelines ML.
* Documentacion que promete produccion live cuando la consigna dice que no se entrega
  servicio live en produccion.
