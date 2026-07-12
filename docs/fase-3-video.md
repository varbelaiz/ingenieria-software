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
  -d '{"well_id": "135204", "as_of_date": "2024-12-31", "horizon_days": 30}' | jq
curl -s http://localhost:8000/api/v1/predictions -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"well_id": "135204", "as_of_date": "2024-12-31", "horizon_days": 90}' | jq
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

## Grabar en Windows (PowerShell)

Los bloques de arriba estan en bash. En Windows con PowerShell hay tres diferencias
que rompen la grabacion si se copian tal cual:

- `$API_KEY` -> `$env:API_KEY`.
- `curl` es alias de `Invoke-WebRequest`; usar `curl.exe` con la sintaxis `-H`/`-d`.
- No hay `jq`; pipear a `python -m json.tool` (viene con el entorno) en vez de `| jq`.

### Prep en un comando

```powershell
pwsh -File scripts/video-fase3-prep.ps1
```

Requiere Docker Desktop abierto. El script crea `.env.data`, levanta ambos stacks,
siembra bronze, corre `dbt build` hasta `ml_features`, verifica el feature store y
**deja `API_KEY`, `WAREHOUSE_*` y `MLFLOW_*` seteadas en esa terminal**. Corre los
pasos siguientes en la MISMA ventana (train/API leen `WAREHOUSE_PORT`, que en el
host es 5433, no el 5432 por defecto).

### Comandos de la demo (misma terminal)

```powershell
# 3. Dos entrenamientos con metricas distintas
uv run --group ml python -m ml.training.train --as-of-date 2024-06-30
$run = uv run --group ml python -m ml.training.train --as-of-date 2024-12-31 | ConvertFrom-Json

# 4. Promocion a champion (toma el run-id del entrenamiento de arriba)
uv run --group ml python -m ml.registry.promote --run-id $run.run_id --max-mae 100

# 5. API con metadata del modelo
uv run uvicorn app.main:app --reload   # dejar corriendo; abrir OTRA terminal prepeada para los curl
curl.exe -s http://localhost:8000/api/v1/models/current -H "X-API-Key: $env:API_KEY" | python -m json.tool
curl.exe -s http://localhost:8000/api/v1/predictions -H "X-API-Key: $env:API_KEY" `
  -H "Content-Type: application/json" `
  -d '{\"well_id\": \"135204\", \"as_of_date\": \"2024-12-31\", \"horizon_days\": 30}' | python -m json.tool
curl.exe -s http://localhost:8000/api/v1/predictions -H "X-API-Key: $env:API_KEY" `
  -H "Content-Type: application/json" `
  -d '{\"well_id\": \"135204\", \"as_of_date\": \"2024-12-31\", \"horizon_days\": 90}' | python -m json.tool
```

> **Wells validos del feature store: `135204`, `200001`, `300001`** (NO `POZO-001`,
> que es del modelo mock viejo de `/forecast` y devuelve 500 en `/predictions`).
>
> La segunda terminal para los `curl` tambien tiene que estar prepeada (correr el
> script de prep ahi, o al menos setear `$env:API_KEY`). El feature store se sirve
> desde Postgres via la API, que necesita `WAREHOUSE_PORT=5433`.

### Notas para grabar

- **MLflow arranca vacio.** El prep resetea MLflow, asi que el experimento y el
  champion se crean en vivo durante la grabacion (pasos 3-4). Metricas esperadas:
  `2024-06-30` -> MAE ~0.58 (15 filas), `2024-12-31` -> MAE ~0.56 (33 filas).
- **Politica de promocion:** se promueve solo si el candidato *mejora* el MAE del
  champion actual. Sobre MLflow limpio la primera promocion siempre entra. Si
  promotes el corte `2024-06-30` (MAE 0.58) y despues `2024-12-31` (0.56), el
  segundo tambien entra (mejora); al reves, el peor queda `rejected` (esperado).
- Si repetis un entrenamiento ya grabado y la promocion sale `rejected`, es porque
  el champion vigente ya es igual o mejor: reseteá con `docker compose -f docker-compose.ml.yml down -v && docker compose -f docker-compose.ml.yml up -d`.

## Capturas sugeridas

- MLflow con multiples runs y sus metricas.
- Dagster con el run de `train_model_job`.
- Respuestas de la API en dos condiciones distintas.
- Tabla `ml_features.well_monthly_features` en Postgres.
- README y ADRs visibles.
