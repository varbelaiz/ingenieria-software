# Plataforma Predictiva de Producción de Hidrocarburos

API REST para consultar pozos disponibles y generar pronósticos mock de producción,
con monitoreo técnico (Prometheus + Grafana) y tráfico sintético (Locust). Sobre esa base,
el proyecto incluye una **plataforma de datos** sobre datos reales de producción de pozos
no convencionales (datos.gob.ar): extracción → medallion (bronze/silver/gold) → modelo
estrella → calidad → gobierno (DataHub) → BI (Metabase), orquestada con Dagster y
transformada con dbt. La arquitectura de datos está en
[`docs/data-platform.md`](docs/data-platform.md).

Stack principal: FastAPI · Python 3.10+ · uv · Docker Compose · Prometheus · Grafana · Terraform (AWS) · Dagster · dbt · PostgreSQL · DataHub · Metabase

## Documentación

La documentación técnica completa está en [`docs/`](docs/index.md):

- [Arquitectura](docs/architecture.md) — componentes, stack y flujo de un request
- [API Reference](docs/api-reference.md) — endpoints, autenticación y ejemplos
- [Plataforma de datos](docs/data-platform.md) — arquitectura medallion, Dagster, dbt, gobierno y BI
- [Modelo de datos](docs/data-model.md) — modelo estrella gold: grano, dimensiones y SCD
- [Infraestructura](docs/infrastructure.md) — recursos AWS y ambientes staging/prod
- [Monitoreo](docs/monitoring.md) — Prometheus, Grafana y métricas
- [Load Testing](docs/load-testing.md) — tráfico sintético con Locust
- [Gobierno de datos](docs/governance.md) — quickstart local de DataHub
- [Ops](docs/ops.md) — deploy, secretos y monitoreo operativo
- [Runbook de Data Engineer](docs/runbooks/data-engineer.md) — backfill histórico y verificación de reprocesos
- [Runbook de BI User](docs/runbooks/bi-user.md) — validar frescura y calidad antes de publicar

## Requisitos

- Python 3.10 o superior
- [uv](https://docs.astral.sh/uv/)
- Docker y Docker Compose

## Inicio rápido local con `uv`

```bash
uv sync
cp .env.example .env   # completar GF_SECURITY_ADMIN_PASSWORD
uv run uvicorn app.main:app --reload
```

Puntos de acceso: API `http://localhost:8000` · Docs `http://localhost:8000/docs`

## Inicio rápido con Docker Compose

```bash
docker compose up --build
```

Servicios: API `:8000` · Prometheus `:9090` · Grafana `:3000`

Credenciales de Grafana: usuario `admin`, contraseña = `GF_SECURITY_ADMIN_PASSWORD` en `.env`.

## Plataforma de datos (Fase 2)

Más allá de la API, el repo incluye una plataforma de datos de extremo a extremo. La
arquitectura completa (flujo medallion, stack, orquestación, calidad) está en
[`docs/data-platform.md`](docs/data-platform.md).

### Levantar el stack de datos y correr los workflows

El stack de datos (warehouse PostgreSQL + Dagster + Metabase) corre localmente vía Docker
Compose; es demasiado pesado para la `t3.micro` de Fase 1, por eso la API y el monitoreo
siguen en AWS y este stack se levanta en local:

```bash
cp .env.data.example .env.data
docker compose --env-file .env.data -f docker-compose.data.yml up --build
```

Servicios: warehouse `:5433` · Dagster `:3001` · Metabase `:3002`

Los workflows se orquestan con Dagster (`http://localhost:3001`). El job
`end_to_end_data_job` carga bronze y corre `dbt build` (silver + gold + tests); el schedule
`monthly_data_pipeline_schedule` lo dispara mensualmente. Para correr o reprocesar una
partición mensual concreta (formato `YYYY-MM-01`):

```bash
docker compose -f docker-compose.data.yml run --rm dagster-webserver \
  dagster job execute -w workspace.yaml -j end_to_end_data_job --partition 2026-05-01
```

El procedimiento completo de backfill y verificación está en el
[Runbook de Data Engineer](docs/runbooks/data-engineer.md).

### Gobierno con DataHub

DataHub corre en un Compose separado del stack principal porque levanta servicios pesados
como Kafka, OpenSearch y MySQL. Para crear las variables locales:

```bash
cp .env.datahub.example .env.datahub
openssl rand -base64 32  # usar para DATAHUB_TOKEN_SERVICE_SIGNING_KEY
openssl rand -base64 32  # usar para DATAHUB_TOKEN_SERVICE_SALT
```

Levantar la UI y los servicios base:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml up -d
```

Acceso local: `http://localhost:9002` con usuario `datahub` y password `datahub`.
Para publicar metadata y revisar lineage/freshness, ver
[`docs/governance.md`](docs/governance.md).

### BI con Metabase

La capa gold se expone a usuarios no tecnicos con [Metabase](https://www.metabase.com/),
conectado al esquema `gold` del warehouse. La decision se documenta en
[ADR-18](docs/ADRs/18-bi-tool.md).

```bash
cp .env.data.example .env.data        # ajustar credenciales si hace falta
docker compose --env-file .env.data -f docker-compose.data.yml up -d

# Esperar a que Metabase este "healthy" (primer arranque tarda ~1 min)
docker compose -f docker-compose.data.yml ps metabase

# Aplicar conexion al warehouse + dashboards de forma idempotente
uv run --group data python -m data_platform.bi.provision
```

Acceso: `http://localhost:3002` (usuario y contrasena = `METABASE_ADMIN_EMAIL` /
`METABASE_ADMIN_PASSWORD` de `.env.data`).

El provisioning es **reproducible y versionado**: las preguntas y el dashboard se definen
en [`data_platform/bi/metabase_config.py`](data_platform/bi/metabase_config.py) y se
aplican con [`data_platform/bi/provision.py`](data_platform/bi/provision.py). Re-ejecutar
el comando converge al mismo estado sin duplicar. El dashboard "Produccion de pozos no
convencionales" incluye produccion de gas por cuenca, petroleo por operadora, top pozos,
evolucion mensual y la marca de calidad de los datos.

## Testing y calidad

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run pre-commit run --all-files
```
