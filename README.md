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
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
```

4. Ejecutar el servidor:

```bash
uv run uvicorn app.main:app --reload
```

## Setup local con Docker Compose

Para levantar la API, Prometheus y Grafana con un solo comando en un stack local
mas cercano al runtime de cloud:

1. Crear o completar `.env`:

```bash
cp .env.example .env
```

2. Levantar el stack completo:

```bash
docker compose up --build
```

Servicios disponibles:

- API: `http://localhost:8000`
- Health: `http://localhost:8000/healthz`
- Metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Este compose usa una imagen independiente por unidad:

- `app` corre standalone, sin bind mounts ni `--reload`
- `prometheus` bakea `prometheus/prometheus.yml` en su propia imagen
- `grafana` bakea provisioning y dashboards en su propia imagen
- Prometheus scrapea al servicio `app` dentro de la red interna default de Compose

## Monitoreo técnico Fase 1

La base de monitoreo técnico usa:

- `/healthz` expuesto por la API para health checks de infraestructura
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

1. Crear o completar `.env`:

```bash
cp .env.example .env
```

2. Levantar API, Prometheus y Grafana:

```bash
docker compose up --build
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

El stack principal se sigue levantando con un solo comando:

```bash
docker compose up --build
```

`locust` no forma parte de ese compose. Se ejecuta aparte, en un contenedor
dedicado, para poblar el dashboard o exigir la API solamente cuando se quiere
testear.

La imagen se construye una vez:

```bash
docker build -t forecast-traffic ./load
```

Variables documentadas para `locust`:

- `LOCUST_HOST`
- `API_KEY`

Antes del primer uso local, crear el env file dedicado:

```bash
cp load/env/local.docker.env.example load/env/local.docker.env
```

El runner usa tres presets:

- `ui`: abre la interfaz web de Locust para explorar manualmente desde el navegador
- `normal`: genera tráfico liviano/normal para poblar monitoreo y validar comportamiento
- `intense`: genera tráfico moderadamente agresivo para exigir más a la app

Todos comparten el mismo modelo de tráfico:

- una siembra corta al inicio del run para garantizar requests `200`, `403` y `404`
- luego un mix ponderado aleatorio donde predominan requests exitosos a `forecast`

### Preset `ui`

Camino recomendado para exploración manual:

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  -p 8089:8089 \
  forecast-traffic \
  --config /load/config/ui.conf
```

Luego abrir:

```text
http://127.0.0.1:8089
```

### Preset `normal`

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  forecast-traffic \
  --config /load/config/normal.conf
```

### Preset `intense`

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  forecast-traffic \
  --config /load/config/intense.conf
```

### Cuándo correr Locust en AWS

Localmente está bien para:

- explorar la UI
- hacer smoke tests
- poblar el dashboard en demos o validaciones rápidas

Si la API está en AWS, conviene correr el contenedor de `locust` cerca de la
API cuando quieras:

- una latencia más representativa
- mayor carga
- acceso a una API privada dentro de una VPC

Preparar un env file remoto:

```bash
cp load/env/aws.env.example load/env/aws.env
```

Ejemplo de ejecución remota:

```bash
docker run --rm \
  --env-file load/env/aws.env \
  forecast-traffic \
  --config /load/config/intense.conf
```

Alternativa secundaria sin Docker para Locust:

```bash
LOCUST_HOST=http://127.0.0.1:8000 \
API_KEY=api_key \
uv run locust -f load/locustfile.py --config load/config/ui.conf
```

### Nota sobre recursos del servicio

`Prometheus Scrape Status` indica si Prometheus puede obtener métricas desde el target configurado. No equivale, por sí solo, a una validación funcional completa del servicio.

`API Process Resource Usage` muestra métricas del proceso Python de la API:

- memoria residente (`process_resident_memory_bytes`)
- tasa de tiempo de CPU consumido (`rate(process_cpu_seconds_total[5m])`)

Estas métricas describen el proceso instrumentado y no el host completo ni el contenedor de Docker. Si más adelante Fase 1 exige métricas de infraestructura más finas, el siguiente paso mínimo sería agregar exporters del host o contenedor, pero no es necesario para esta base.

## Estructura del proyecto

```
docker-compose.yml       # Stack local canonico: app + prometheus + grafana
prometheus/
├── Dockerfile           # Imagen de Prometheus con config bakeada
└── prometheus.yml       # Config de scrape sobre la API
grafana/
├── Dockerfile           # Imagen de Grafana con provisioning y dashboard
├── dashboards/
└── provisioning/
app/
├── __init__.py          # Paquete principal
├── main.py              # Punto de entrada de FastAPI y registro de routers
├── middleware.py        # Middleware global (validación de API key)
├── forecast/
│   ├── __init__.py      # Exporta el router de pronóstico
│   └── routes.py        # Endpoints de pronóstico de producción
└── wells/
    ├── __init__.py      # Exporta el router de pozos
    └── routes.py        # Endpoints de consulta de pozos
load/
├── Dockerfile           # Imagen separada para ejecutar Locust
├── config/              # Presets ui / normal / intense
├── env/                 # Ejemplos de env files para local Docker y AWS
└── locustfile.py        # Modelo de tráfico compartido por los presets
```

## Autenticación

Los endpoints de negocio requieren el header `X-API-Key` con una clave válida.
La clave se configura mediante la variable de entorno `API_KEY`. Si la clave es
inválida o no se proporciona, se retorna un error `403 Forbidden`.

Excepciones técnicas sin autenticación:

- `GET /healthz` para health checks de infraestructura
- `GET /metrics` para scrapes de Prometheus

`/metrics` se mantiene expuesto para el stack de monitoreo local y más adelante
puede bloquearse públicamente a nivel de ALB sin cambiar la app.

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
