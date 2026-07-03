# Runbook de ML Engineer

**Rol:** ML Engineer
**Responsabilidades:** Materializacion de features, entrenamiento reproducible, tracking de
experimentos, promocion de modelos y disparo de retraining.
**Dueño:** Equipo de ML Engineering.

Este runbook cubre el flujo punta a punta de la Fase 3: desde levantar el stack hasta
disparar un retrain y verlo reflejado en un nuevo run de MLflow y en la API.

## Prerrequisitos

- Docker y Docker Compose disponibles.
- Dependencias instaladas: `uv sync --group data --group ml`.
- Stack de datos y MLflow levantados:

```bash
docker compose --env-file .env.data -f docker-compose.data.yml up -d
docker compose -f docker-compose.ml.yml up -d
```

- Warehouse PostgreSQL en el servicio `warehouse`.
- Dagster UI en `http://localhost:3001`.
- MLflow UI en `http://localhost:5000`.
- Variable `MLFLOW_TRACKING_URI` apuntando al server (por defecto `http://localhost:5000`).
  El stack de datos y el de MLflow corren en redes de compose distintas: al entrenar desde
  la UI de Dagster, asegurarse de que `MLFLOW_TRACKING_URI` sea alcanzable desde el
  contenedor de Dagster (por ejemplo `http://host.docker.internal:5000`).

## 1. Materializar el feature store

Las features se materializan con dbt (`ml_features.well_monthly_features`) a partir de gold.
Se puede hacer desde Dagster (asset `ml_features/well_monthly_features`, incluido en
`end_to_end_data_job`) o directo con dbt:

```bash
uv run --group data python -m data_platform.ci.seed_bronze   # solo en entorno de prueba
uv run --group data dbt build --select silver gold ml_features \
  --project-dir data_platform/transform --profiles-dir data_platform/transform
```

Verificar que hay filas point-in-time por pozo y fecha:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select well_id, as_of_date, gas_production_current
      from ml_features.well_monthly_features
      order by well_id, as_of_date limit 20;"
```

## 2. Entrenar para un `as_of_date`

El entrenamiento lee del feature store (nunca datos futuros respecto de `as_of_date`),
ajusta el modelo baseline y registra params, metricas y artefacto en MLflow:

```bash
uv run --group ml python -m ml.training.train --as-of-date 2024-12-31
```

Imprime un JSON con `run_id` y `metrics` (MAE, RMSE, filas). Guardar el `run_id`.

## 3. Ver runs y metricas en MLflow

Abrir `http://localhost:5000`, entrar al experimento `well-production-forecast` y comparar
runs. Cada run trae los tags de reproducibilidad: `as_of_date`, `dataset_start`,
`dataset_end`, `feature_view`, `model_type`.

## 4. Promover o ver el modelo vigente

Registrar el run como candidato y evaluarlo contra la politica de MAE. Si pasa el umbral y
mejora al champion actual, se mueve el alias `champion`:

```bash
uv run --group ml python -m ml.registry.promote --run-id <RUN_ID> --max-mae 100
```

Consultar el modelo vigente por API:

```bash
uv run uvicorn app.main:app --reload
curl -s http://localhost:8000/api/v1/models/current -H "X-API-Key: $API_KEY" | jq
```

Si no hay modelo promovido, el endpoint responde `503`.

## 5. Llamar a la API de predicciones

```bash
curl -s http://localhost:8000/api/v1/predictions \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"well_id": "POZO-001", "as_of_date": "2024-12-31", "horizon_days": 30}' | jq
```

La respuesta incluye la prediccion, la metadata del modelo (version, run_id, alias,
metricas) y `feature_as_of_date`, para trazabilidad completa.

## 6. Disparar un retrain

El retrain esta orquestado en Dagster como `train_model_job` (assets `ml_trained_model` ->
`ml_promoted_model`), particionado por mes.

- **Manual:** en la UI de Dagster (`http://localhost:3001`), abrir `train_model_job`,
  seleccionar la particion (`YYYY-MM-01`) y lanzar la materializacion.
- **Recurrente:** el schedule `ml_retraining_schedule` corre mensualmente el dia 2 a las
  04:00 ART sobre la ultima particion mensual cerrada.

Despues del retrain, verificar un nuevo run en MLflow y, si fue promovido, que
`GET /api/v1/models/current` refleje la nueva version.

## Equivalentes locales de los checks de CI

```bash
# Validar que las Definitions de Dagster cargan (incluye los assets ML)
uv run --group data --group ml dagster definitions validate -m data_platform.orchestration

# Tests de orquestacion ML (in-memory + MLflow file-store, sin infra)
uv run --group data --group ml pytest tests/test_ml_orchestration.py

# Smoke de training punta a punta contra el warehouse, sin server MLflow
uv run --group data python -m data_platform.ci.seed_bronze
uv run --group data dbt build --select silver gold ml_features \
  --project-dir data_platform/transform --profiles-dir data_platform/transform
MLFLOW_TRACKING_URI=file:./mlruns uv run --group ml python -m ml.training.train --as-of-date 2024-12-31
```

## Manejo de fallos

### El training falla con "insufficient training data"

`build_training_dataset` necesita al menos dos snapshots mensuales por pozo antes del
`as_of_date` para formar pares feature/target. Verificar que `ml_features` tenga historia
suficiente para la fecha elegida (paso 1) y elegir un `as_of_date` posterior a esos periodos.

### La promocion rechaza el candidato

Es el comportamiento esperado cuando el MAE supera el umbral o no mejora al champion. Revisar
el `reason` que imprime `ml.registry.promote` y las metricas del run en MLflow. Un candidato
rechazado no reemplaza al modelo vigente.

### El asset de training no encuentra features

El asset `ml_trained_model` depende del modelo dbt `ml_features`. Si la particion de features
no fue materializada, materializar primero el feature store (paso 1) o correr
`end_to_end_data_job` para esa particion.
