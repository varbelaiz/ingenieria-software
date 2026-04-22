# Plataforma Predictiva de Producción de Hidrocarburos

Sistema para pronosticar la producción futura de hidrocarburos, reduciendo la incertidumbre en la planificación operativa mediante modelos predictivos y una API REST para consulta e integración.

## Requisitos

- Python 3.10+
- [UV](https://docs.astral.sh/uv/) como package manager

## Setup local

1. Clonar el repositorio:

```bash
git clone <repo-url>
cd ingenieria-software
```

2. Instalar dependencias:

```bash
uv sync
```

3. Configurar variables de entorno:

```bash
cp .env.example .env
```

Editar `.env` con los valores correspondientes:

```
API_KEY=api_key
```

4. Ejecutar el servidor:

```bash
uv run uvicorn app.main:app --reload
```

## Setup local con Docker Compose

Para levantar la API, Prometheus y Grafana con un solo comando en modo desarrollo:

1. Copiar variables de entorno para Compose:

```bash
cp .env.compose.example .env.compose
```

2. Levantar el stack completo:

```bash
docker compose -f docker-compose.monitoring.yml up --build
```

Servicios disponibles:

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Esta variante esta pensada para desarrollo local:

- la API corre dentro de Docker
- el codigo del repo se monta como volumen
- `uvicorn` corre con `--reload`
- Prometheus scrapea al servicio `api` dentro de la red de Compose

## Monitoreo técnico Fase 1

La base de monitoreo técnico usa:

- `/metrics` expuesto por la API en formato Prometheus
- Prometheus local para scrappear métricas de la API
- Grafana provisionado con un dashboard inicial de Fase 1

### Métricas cubiertas

- Estado de scrape de Prometheus sobre la API (`up`)
- Latencia de requests exitosos del endpoint `GET /api/v1/forecast`
- Tasa de errores HTTP (`4xx/5xx`)
- Frecuencia de requests a la API
- Uso de recursos del proceso Python expuesto en `/metrics`

### Levantar monitoreo local

1. Copiar variables de entorno de Compose:

```bash
cp .env.compose.example .env.compose
```

2. Levantar API, Prometheus y Grafana:

```bash
docker compose -f docker-compose.monitoring.yml up --build
```

3. Abrir Grafana en `http://localhost:3000` con:

```text
usuario: admin
password: admin
```

4. Abrir el dashboard provisionado:

```text
Fase 1 / Fase 1 - Technical Monitoring
```

### Generar tráfico de prueba

Para poblar el dashboard automáticamente con requests exitosas y con error:

```bash
uv run python scripts/generate_monitoring_traffic.py
```

El script se sigue ejecutando desde el host y apunta a `http://localhost:8000`.

El script genera, por ciclo:

- `GET /api/v1/wells` exitoso
- `GET /api/v1/forecast` exitoso
- `GET /api/v1/wells` con API key inválida (`403`)
- `GET /api/v1/forecast` con pozo inexistente (`404`)

Opciones útiles:

```bash
uv run python scripts/generate_monitoring_traffic.py --cycles 10 --pause-seconds 1
uv run python scripts/generate_monitoring_traffic.py --api-url http://127.0.0.1:8000 --api-key api_key
```

### Tráfico sintético con `k6`

Además del script Python de smoke/demo, el repo incluye una base desacoplada de
tráfico sintético en [load/traffic.js](/Users/franco/Documentos/UdeSA Local/4to año/1er semestre/Ing. Software/ingenieria-software/load/traffic.js).

Configuración por variables de entorno:

- `API_BASE_URL` (default: `http://127.0.0.1:8000`)
- `API_KEY` (default: `api_key`)
- `TRAFFIC_PROFILE` (`seed` o `realistic`, default: `seed`)

Perfil `seed`:

```bash
API_BASE_URL=http://127.0.0.1:8000 \
API_KEY=api_key \
TRAFFIC_PROFILE=seed \
k6 run load/traffic.js
```

Perfil `realistic`:

```bash
API_BASE_URL=http://127.0.0.1:8000 \
API_KEY=api_key \
TRAFFIC_PROFILE=realistic \
k6 run load/traffic.js
```

El perfil `seed` genera un patrón determinístico que garantiza tráfico `200`,
`403` y `404` para mantener visibles los paneles actuales de Grafana.

El perfil `realistic` usa una mezcla ponderada donde predominan requests
exitosos a `forecast`, con menor proporción de `wells`, `403` y `404`.

### Ejecutar el traffic generator en contenedor

Esta primera versión no forma parte del compose principal y se mantiene
desacoplada de la API.

Build de la imagen:

```bash
docker build -t forecast-traffic ./load
```

Run contra una API local:

```bash
docker run --rm \
  -e API_BASE_URL=http://host.docker.internal:8000 \
  -e API_KEY=api_key \
  -e TRAFFIC_PROFILE=seed \
  forecast-traffic
```

Run contra una API remota:

```bash
docker run --rm \
  -e API_BASE_URL=https://your-api.example.com \
  -e API_KEY=your_api_key \
  -e TRAFFIC_PROFILE=realistic \
  forecast-traffic
```

### Nota sobre recursos del servicio

`Prometheus Scrape Status` indica si Prometheus puede obtener métricas desde el target configurado. No equivale, por sí solo, a una validación funcional completa del servicio.

`API Process Resource Usage` muestra métricas del proceso Python de la API:

- memoria residente (`process_resident_memory_bytes`)
- tasa de tiempo de CPU consumido (`rate(process_cpu_seconds_total[5m])`)

Estas métricas describen el proceso instrumentado y no el host completo ni el contenedor de Docker. Si más adelante Fase 1 exige métricas de infraestructura más finas, el siguiente paso mínimo sería agregar exporters del host o contenedor, pero no es necesario para esta base.

## Estructura del proyecto

```
app/
├── __init__.py          # Paquete principal
├── main.py              # Punto de entrada de FastAPI y registro de routers
├── middleware.py         # Middleware global (validación de API key)
├── forecast/
│   ├── __init__.py      # Exporta el router de pronóstico
│   └── routes.py        # Endpoints de pronóstico de producción
└── wells/
    ├── __init__.py      # Exporta el router de pozos
    └── routes.py        # Endpoints de consulta de pozos
```

## Autenticación

Todos los endpoints requieren el header `X-API-Key` con una clave válida. La clave se configura mediante la variable de entorno `API_KEY`. Si la clave es inválida o no se proporciona, se retorna un error `403 Forbidden`.

## Endpoints

### `GET /api/v1/wells`

Retorna la lista de pozos disponibles para una fecha determinada.

**Parámetros de query:**

| Parámetro    | Tipo   | Requerido | Descripción                  |
|--------------|--------|-----------|------------------------------|
| `date_query` | `date` | Sí        | Fecha en formato `YYYY-MM-DD` |

**Ejemplo de respuesta:**

```json
{
  "date_query": "2026-03-23",
  "wells": ["POZO-001", "POZO-002", "POZO-003"]
}
```

### `GET /api/v1/forecast`

Retorna un pronóstico de producción (tendencia lineal decreciente) para un pozo en un rango de fechas.

**Parámetros de query:**

| Parámetro    | Tipo   | Requerido | Descripción                        |
|--------------|--------|-----------|------------------------------------|
| `id_well`    | `str`  | Sí        | Identificador del pozo             |
| `date_start` | `date` | Sí        | Fecha inicial en formato `YYYY-MM-DD` |
| `date_end`   | `date` | Sí        | Fecha final en formato `YYYY-MM-DD`   |

**Ejemplo de respuesta:**

```json
{
  "id_well": "POZO-001",
  "date_start": "2026-03-01",
  "date_end": "2026-03-03",
  "trend": "linear_decreasing",
  "data": [
    {"date": "2026-03-01", "oil_bopd": 1200.0},
    {"date": "2026-03-02", "oil_bopd": 1192.5},
    {"date": "2026-03-03", "oil_bopd": 1185.0}
  ]
}
```

**Errores posibles:**

| Código | Descripción                                    |
|--------|------------------------------------------------|
| `404`  | Pozo no encontrado                             |
| `400`  | `date_end` debe ser mayor o igual a `date_start` |
