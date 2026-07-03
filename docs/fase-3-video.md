# Guion y evidencia del video — Fase 3

El video dura entre 5 y 10 minutos y debe demostrar la integracion real del proceso de ML
Engineering con la API de predicciones, no solo slides. Esta guia lista que mostrar, que
decir y los comandos exactos.

## Preparacion (antes de grabar)

```bash
docker compose --env-file .env.data -f docker-compose.data.yml up -d
docker compose -f docker-compose.ml.yml up -d
uv run --group data python -m data_platform.ci.seed_bronze
uv run --group data dbt build --select silver gold ml_features \
  --project-dir data_platform/transform --profiles-dir data_platform/transform
```

Dejar abiertos: Dagster (`http://localhost:3001`), MLflow (`http://localhost:5000`) y una
terminal con `API_KEY` exportada.

## Evidencia minima a tener lista

- Feature store persistido en Postgres (`ml_features.well_monthly_features`).
- MLflow con al menos dos runs con metricas distintas.
- Un modelo registrado y promovido a `champion`.
- Llamadas a la API con dos condiciones distintas.
- Trigger de retrain en Dagster para un `as_of_date`.

## Orden recomendado

### 1. Arquitectura (que decir)

Mostrar la seccion "Plataforma ML Engineering (Fase 3)" del `README.md`. Explicar el flujo
gold -> feature store -> training/validation -> MLflow tracking + registry -> API, y por que
el feature store se puebla con dbt aguas arriba (evitar train/serve skew). Mencionar que la
entrega no tiene servicio live y que el "despliegue" de pipelines es via CI + Dagster.

### 2. Feature store (que mostrar)

```bash
docker compose -f docker-compose.data.yml exec warehouse psql -U warehouse -d warehouse \
  -c "select well_id, as_of_date, gas_production_current, gas_production_avg_3m
      from ml_features.well_monthly_features order by well_id, as_of_date limit 15;"
```

Decir: las mismas features las consume training e inferencia.

### 3. Dos entrenamientos con metricas distintas (que mostrar)

```bash
uv run --group ml python -m ml.training.train --as-of-date 2024-06-30
uv run --group ml python -m ml.training.train --as-of-date 2024-12-31
```

Abrir MLflow, experimento `well-production-forecast`, comparar los dos runs y sus metricas
(MAE, RMSE) y los tags de reproducibilidad.

### 4. Registro y promocion (que mostrar)

```bash
uv run --group ml python -m ml.registry.promote --run-id <RUN_ID> --max-mae 100
```

Mostrar en MLflow el modelo con alias `champion`.

### 5. API respondiendo con metadata del modelo (que mostrar)

```bash
uv run uvicorn app.main:app --reload
curl -s http://localhost:8000/api/v1/models/current -H "X-API-Key: $API_KEY" | jq
curl -s http://localhost:8000/api/v1/predictions -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"well_id": "POZO-001", "as_of_date": "2024-12-31", "horizon_days": 30}' | jq
curl -s http://localhost:8000/api/v1/predictions -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"well_id": "POZO-001", "as_of_date": "2024-12-31", "horizon_days": 90}' | jq
```

Resaltar la trazabilidad: `version`, `run_id`, `alias` y `feature_as_of_date` en la
respuesta.

### 6. Trigger de retrain en Dagster (que mostrar)

En la UI de Dagster, abrir `train_model_job`, elegir una particion mensual y lanzar la
materializacion de `ml_trained_model` -> `ml_promoted_model`. Mostrar el run exitoso.

### 7. Nuevo run post-retrain (que mostrar)

Volver a MLflow y mostrar el run nuevo generado por el job de Dagster. Opcional: repetir
`GET /api/v1/models/current` para ver si cambio la version vigente.

### 8. Cierre (que decir)

Resumir el valor agregado: reproducibilidad (entrenar cualquier `as_of_date`), trazabilidad
(run -> metricas -> modelo servido) y reduccion de skew (una sola fuente de features para
training e inferencia).

## Capturas sugeridas

- MLflow con multiples runs y sus metricas.
- Dagster con el run de `train_model_job`.
- Respuestas de la API en dos condiciones distintas.
- Tabla `ml_features.well_monthly_features` en Postgres.
- README y ADRs visibles.
