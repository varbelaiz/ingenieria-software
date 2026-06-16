# Plataforma de datos (Fase 2)

## Qué resuelve

La plataforma de datos toma datos reales de producción de pozos no convencionales de
Argentina (datos.gob.ar) y los lleva de extremo a extremo: **extraer → bronze → silver →
gold → calidad → gobierno / BI**. El resultado es un modelo estrella consultable por
usuarios no técnicos, con checks de calidad persistidos, lineage navegable y orquestación
reprocesable por fecha.

Es el eje de la Fase 2: la Fase 1 (API FastAPI + monitoreo Prometheus/Grafana, ver
[Arquitectura](architecture.md)) se mantiene; esta capa se suma sobre la misma base de
Docker Compose, CI con GitHub Actions y Git Flow.

## Diagrama de flujo

```
datos.gob.ar                         ┌───────────── Dagster (orquestación) ─────────────┐
  ├─ producción (CSV) ──┐            │  end_to_end_data_job   (schedule mensual)        │
  └─ pozos (CSV) ───────┤            │  data_quality_job      (gate de calidad)         │
                        ▼            └──────────────────────────────────────────────────┘
              extraction/ (HTTP + retry)            │
                        │  load_bronze_*            │ dbt build --select silver gold
                        ▼                           ▼
   ┌──────────────────── PostgreSQL warehouse (:5433) ────────────────────┐
   │  bronze   landing crudo, particionado mensual, idempotente           │
   │     │  dbt (incremental merge)                                       │
   │  silver   limpieza, tipado, deduplicación, conformado                │
   │     │  dbt (modelo estrella)                                         │
   │  gold     dim_* + fct_produccion + quality_marks                     │
   └──────────────┬───────────────────────────────┬──────────────────────┘
                  │                                │
                  ▼                                ▼
        Metabase (BI, :3002)            DataHub (gobierno, :9002)
        dashboards sobre gold           lineage + freshness por tabla
```

El diagrama interactivo de la arquitectura de datos está en
[`docs/ADRs/diagram-data-architecture.html`](ADRs/diagram-data-architecture.html).

## Stack tecnológico

| Capa | Herramienta | ADR |
|------|-------------|-----|
| Orquestación | **Dagster** (assets + jobs + schedule) | [ADR-11](ADRs/11-orchestration-tool.md) |
| Warehouse | **PostgreSQL** | [ADR-12](ADRs/12-warehouse-engine.md) |
| Medallion / transformación | **dbt (dbt-postgres)** | [ADR-13](ADRs/13-medallion-layering.md) |
| Tipo de carga | **incremental merge / upsert** | [ADR-14](ADRs/14-load-type.md) |
| Modelo dimensional | **estrella** (dims + fact) | [ADR-15](ADRs/15-dimensional-model.md) |
| Calidad | **dbt tests + dbt-expectations + `store_failures`** | [ADR-16](ADRs/16-data-quality.md) |
| Gobierno | **DataHub** | [ADR-17](ADRs/17-data-governance.md) |
| BI | **Metabase** | [ADR-18](ADRs/18-bi-tool.md) |

## Capas medallion

Las tres capas viven en esquemas homónimos de la misma base Postgres
(`data_platform/transform/dbt_project.yml`):

- **bronze** — landing del dato crudo, sin transformar. Lo escriben los assets de
  extracción de Dagster (`data_platform/extraction/`, `data_platform/orchestration/assets/bronze.py`),
  particionado mensual. La escritura reemplaza la partición antes de insertar, por lo que
  re-correr un período no duplica filas. Las fuentes se declaran en
  `data_platform/transform/models/sources.yml` con `loaded_at_field: _loaded_at` para
  freshness.
- **silver** — limpieza, tipado, deduplicación y conformado (`models/silver/stg_produccion.sql`,
  `stg_pozos.sql`). `stg_produccion` es incremental con estrategia `merge` por
  `(id_pozo, periodo)`, para absorber las correcciones retroactivas de la fuente.
- **gold** — modelo estrella listo para consumo: `fct_produccion` (grano un pozo × un mes),
  seis dimensiones y la vista `quality_marks`. El detalle de grano, dimensiones, surrogate
  keys y estrategia SCD está en [Modelo de datos gold](data-model.md).

## Orquestación

Dagster define dos jobs y un schedule (`data_platform/orchestration/`):

- **`end_to_end_data_job`** — carga bronze (producción + pozos) y luego corre
  `dbt build --select silver gold` (modelos + tests). Está particionado por mes; reprocesar
  una fecha = re-materializar su partición.
- **`data_quality_job`** — corre `dbt source freshness` y `dbt build` como gate de calidad
  aislado.
- **`monthly_data_pipeline_schedule`** — dispara `end_to_end_data_job` con cron
  `0 3 1 * *` (TZ `America/Argentina/Buenos_Aires`) sobre la última partición mensual
  cerrada.

Todos los ops usan `RetryPolicy(max_retries=3, delay=30, backoff=Backoff.EXPONENTIAL)`
para tolerar fallos transitorios (locks del warehouse, timeouts HTTP a datos.gob.ar). La
UI de Dagster (`http://localhost:3001`) da logs y status por corrida.

## Calidad de datos

- Los tests dbt cubren completitud, unicidad, validez, schema y frescura sobre silver y
  gold (`models/gold/_gold__models.yml`).
- `store_failures: true` (esquema `dbt_test_failures`) **persiste** las filas que fallan
  cada test, no solo el pass/fail.
- La vista `gold.quality_marks` resume el último estado de cada check (`status` `PASS` /
  `ERROR`, `failed_rows`, `checked_at`): es la marca de calidad visible para BI y gobierno.
- Usar `dbt build` (no `run`) hace que un test fallido **corte la corrida y bloquee la
  promoción** a gold. Un `failure_hook` de Dagster emite una alerta estructurada (y la
  reenvía a un webhook si `DATA_QUALITY_ALERT_WEBHOOK_URL` está configurada).

## Gobierno y BI

- **Gobierno (DataHub):** lineage a nivel tabla (`bronze → silver → gold`), freshness y
  workflows visibles. Levantado, recetas de ingesta y verificación en
  [Gobierno de datos](governance.md).
- **BI (Metabase):** dashboards sobre el esquema `gold` para usuarios no técnicos. La
  conexión al warehouse y los dashboards se aplican de forma reproducible con
  `data_platform/bi/provision.py` (ver el [README](../README.md#bi-con-metabase)).

## Cómo correr y actualizar los workflows

Levantar el stack de datos (warehouse + Dagster + Metabase):

```bash
cp .env.data.example .env.data
docker compose --env-file .env.data -f docker-compose.data.yml up --build
```

Abrir Dagster en `http://localhost:3001` y materializar/ejecutar el job. Para correr o
reprocesar una partición mensual concreta (formato `YYYY-MM-01`):

```bash
docker compose -f docker-compose.data.yml run --rm dagster-webserver \
  dagster job execute -w workspace.yaml -j end_to_end_data_job --partition 2026-05-01
```

El schedule mensual queda registrado automáticamente; alcanza con activarlo desde la UI de
Dagster. El procedimiento completo de backfill y verificación está en el
[Runbook de data engineer](runbooks/data-engineer.md).

Para correr dbt directamente desde la raíz del repo (sin Docker), contra el warehouse
local:

```bash
uv run --group data dbt build \
  --select silver gold \
  --project-dir data_platform/transform \
  --profiles-dir data_platform/transform
```

## Puertos

| Servicio | Puerto | Compose file |
|----------|--------|--------------|
| Warehouse (PostgreSQL) | `5433` | `docker-compose.data.yml` |
| Dagster webserver | `3001` | `docker-compose.data.yml` |
| Metabase | `3002` | `docker-compose.data.yml` |
| DataHub frontend | `9002` | `docker-compose.datahub.yml` |

DataHub corre en un Compose separado por su peso (Kafka + OpenSearch + MySQL); por eso el
stack de datos de Fase 2 corre **localmente**, mientras la API y el monitoreo de Fase 1
siguen en AWS.

## Documentación relacionada

- [Modelo de datos gold](data-model.md) — grano, dimensiones, surrogate keys y SCD.
- [Gobierno de datos](governance.md) — DataHub: ingesta, lineage y freshness.
- [Runbook de data engineer](runbooks/data-engineer.md) — backfill y reproceso histórico.
- [Runbook de BI user](runbooks/bi-user.md) — validar frescura y calidad antes de publicar.
- ADRs [11](ADRs/11-orchestration-tool.md)–[18](ADRs/18-bi-tool.md) — decisiones del stack de datos.
