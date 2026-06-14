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
- [Ops](docs/ops.md) — deploy, secretos y monitoreo operativo

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

## Testing y calidad

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run pre-commit run --all-files
```
