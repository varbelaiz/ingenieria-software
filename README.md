# Plataforma Predictiva de Producción de Hidrocarburos

API REST para consultar pozos disponibles y generar pronósticos mock de producción,
con monitoreo técnico (Prometheus + Grafana) y tráfico sintético (Locust).

Stack principal: FastAPI · Python 3.10+ · uv · Docker Compose · Prometheus · Grafana · Terraform (AWS)

## Documentación

La documentación técnica completa está en [`docs/`](docs/index.md):

- [Arquitectura](docs/architecture.md) — componentes, stack y flujo de un request
- [API Reference](docs/api-reference.md) — endpoints, autenticación y ejemplos
- [Infraestructura](docs/infrastructure.md) — recursos AWS y ambientes staging/prod
- [Monitoreo](docs/monitoring.md) — Prometheus, Grafana y métricas
- [Load Testing](docs/load-testing.md) — tráfico sintético con Locust
- [Gobierno de datos](docs/governance.md) — quickstart local de DataHub
- [Ops](docs/ops.md) — deploy, secretos y monitoreo operativo
- [Runbook de Data Engineer](docs/runbooks/data-engineer.md) — backfill histórico y verificación de reprocesos

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

## DataHub local

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

## Plataforma de BI (Metabase)

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

El provisioning tambien elimina el contenido de ejemplo que trae Metabase (la "Sample
Database" y su dashboard), dejando la instancia limpia. El compose sube el tope de filas
por query (`MB_*_QUERY_ROW_LIMIT`) por encima del default de 2000 para que ninguna card se
trunque silenciosamente al crecer los datos. Las credenciales por defecto
(`METABASE_ADMIN_*`, `MB_ENCRYPTION_SECRET_KEY`, `metabase_ro`) son solo para uso local:
rotalas y usa un secreto aleatorio real en cualquier despliegue compartido.
## Plataforma de datos (Dagster)

El pipeline corre como un grafo de assets de Dagster: los assets de bronze
(`bronze_produccion_raw`, `bronze_pozos_raw`) alimentan los modelos dbt de silver y gold,
expuestos como assets vía `dagster-dbt` (`silver/stg_produccion`, `gold/fct_produccion`,
etc.), con los tests dbt como asset checks. Para actualizar los workflows, materializar la
partición mensual desde la UI de Dagster (`http://localhost:3001`) o esperar al schedule
`monthly_data_pipeline_schedule`. El manifest de dbt se genera en el build de la imagen
(`Dockerfile.dagster`) y en CI antes de validar las Definitions.

## Testing y calidad

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run pre-commit run --all-files
```
