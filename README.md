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

## Testing y calidad

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run pre-commit run --all-files
```
