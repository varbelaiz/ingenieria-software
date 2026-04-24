# Plataforma Predictiva de Producción de Hidrocarburos

API REST para consultar pozos disponibles y generar pronósticos mock de producción.
El repositorio también incluye una base de monitoreo técnico con Prometheus y Grafana,
y un runner separado de tráfico sintético con Locust.

## Qué resuelve y stack principal

Este proyecto centraliza una API simple para exponer información operativa y
proveer un punto de integración para pruebas, monitoreo y validaciones locales.

Stack principal:

- FastAPI para la API REST
- Python 3.10+ y [uv](https://docs.astral.sh/uv/) para entorno y dependencias
- Docker Compose para levantar el stack local
- Prometheus y Grafana para monitoreo técnico
- Locust para tráfico sintético, documentado en [`load/README.md`](load/README.md)

## Requisitos

- Python 3.10 o superior
- [uv](https://docs.astral.sh/uv/)
- Docker y Docker Compose para el stack completo de monitoreo

## Inicio rápido local con `uv`

1. Clonar el repositorio y entrar al directorio del proyecto:

```bash
git clone <repo-url>
cd ingenieria-software
```

2. Instalar dependencias:

```bash
uv sync
```

3. Crear el archivo de entorno local:

```bash
cp .env.example .env
```

`.env.example` trae valores base para desarrollo local. Completá la contraseña de Grafana en tu `.env`; ese archivo está ignorado por git y no debe commitearse.

```env
API_KEY=api_key
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=<tu-password-local>
```

4. Levantar la API en modo desarrollo:

```bash
uv run uvicorn app.main:app --reload
```

Puntos de acceso útiles:

- API: `http://localhost:8000`
- Documentación interactiva: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/healthz`
- Métricas: `http://localhost:8000/metrics`

## Inicio rápido con Docker Compose

Con el mismo archivo `.env`, podés levantar la API junto con Prometheus y Grafana:

```bash
docker compose up --build
```

Servicios disponibles:

- API: `http://localhost:8000`
- Documentación interactiva: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/healthz`
- Métricas: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Credenciales locales de Grafana:

```text
usuario: admin
password: el valor de GF_SECURITY_ADMIN_PASSWORD en tu .env
```

Notas del stack local:

- `api` corre como servicio independiente dentro de Compose
- `prometheus` usa la configuración bakeada en `prometheus/prometheus.yml`
- `grafana` se levanta con datasource y dashboard provisionados
- Locust no forma parte de `docker compose up --build`; se ejecuta por separado

## Testing y calidad

Comandos útiles para validar el proyecto localmente:

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run pre-commit run --all-files
```

La pipeline de CI ejecuta tests y hooks de `pre-commit` con esta misma base.

## Deploy y secretos

Terraform crea secretos por ambiente en AWS Secrets Manager para `API_KEY` y la
contraseña admin de Grafana. Pasalos como variables sensibles, por ejemplo con
`TF_VAR_api_key` y `TF_VAR_grafana_admin_password`, sin commitear valores reales.

En cada deploy, la EC2 regenera `/opt/app/.env` desde Secrets Manager antes de
levantar el stack. Grafana usa `GF_SECURITY_ADMIN_USER=admin` y
`GF_SECURITY_ADMIN_PASSWORD` desde ese archivo; si el volumen ya existía, el
deploy también resincroniza la contraseña del usuario admin dentro del contenedor.

## Estructura resumida del proyecto

```text
app/
├── main.py              # Entrada de FastAPI y registro de routers
├── middleware.py        # Validación global de API key
├── health.py            # Health check técnico
├── monitoring.py        # Métricas Prometheus
├── forecast/            # Endpoint de pronóstico
└── wells/               # Endpoint de consulta de pozos
grafana/
├── dashboards/          # Dashboard provisionado
└── provisioning/        # Datasource y carga automática
prometheus/
└── prometheus.yml       # Configuración de scrape local
load/
├── config/              # Presets de Locust
├── env/                 # Env files de ejemplo
├── locustfile.py        # Runner de tráfico sintético
└── README.md            # Documentación específica de Locust
tests/                   # Suite de tests
Dockerfile               # Imagen de la API
docker-compose.yml       # Stack local de API + Prometheus + Grafana
pyproject.toml           # Configuración del proyecto y dependencias
```

Además, el repo conserva directorios auxiliares como `app/static/` y `app/dashboard/`.

## Autenticación y endpoints

Los endpoints de negocio requieren el header `X-API-Key`. El valor esperado se
configura con la variable de entorno `API_KEY`.

Endpoints principales:

- `GET /api/v1/wells`: devuelve la lista de pozos disponibles para una fecha.
- `GET /api/v1/forecast`: devuelve un pronóstico mock de producción para un pozo y un rango de fechas.
- `GET /healthz`: expone un health check técnico sin autenticación.
- `GET /metrics`: expone métricas en formato Prometheus sin autenticación.

Los endpoints `GET /api/v1/wells` y `GET /api/v1/forecast` también están
documentados en `http://localhost:8000/docs`, que es la referencia recomendada
para revisar parámetros, validaciones y respuestas del contrato OpenAPI.

## Documentación relacionada

- [`load/README.md`](load/README.md): uso del runner de tráfico sintético con Locust.
- `grafana/`: dashboard y provisioning del stack de monitoreo local.
- `prometheus/`: configuración de scrape para la API.
