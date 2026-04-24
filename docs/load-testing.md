# Load Testing

## Qué es Locust

[Locust](https://locust.io/) es una herramienta de load testing que simula usuarios concurrentes haciendo requests HTTP a una API. En este proyecto se usa para dos propósitos: generar tráfico sintético que puebla el dashboard de Grafana/Prometheus y validar el comportamiento de la API bajo carga.

## Mix de tráfico

El tráfico simulado replica un patrón realista de uso:

| Escenario | Proporción | Descripción |
|-----------|------------|-------------|
| Forecast exitoso | 75% | `GET /api/v1/forecast` con pozo y fechas válidos |
| Wells exitoso | 18% | `GET /api/v1/wells` con fecha válida |
| API key inválida | 4% | Request con key incorrecta → 403 |
| Pozo inexistente | 3% | `GET /api/v1/forecast` con id_well inválido → 404 |

Antes de entrar al loop principal, cada usuario ejecuta un **seed** de escenarios deterministas para asegurarse de que los paneles del dashboard tengan datos desde el inicio.

## Presets

Los presets viven en `load/config/` y se pasan con `--config`.

| Preset | Modo | Uso recomendado |
|--------|------|-----------------|
| `ui` | Interfaz web en `:8089` | Exploración manual y demos |
| `normal` | Headless, carga liviana | Poblar monitoreo, validación base |
| `intense` | Headless, carga alta | Stress test sin ser destructivo |

## Ejecución local (Docker)

```bash
# 1. Levantar el stack principal
docker compose up --build

# 2. Construir la imagen de Locust
docker build -t forecast-traffic ./load

# 3. Crear el archivo de entorno (una sola vez)
cp load/env/local.docker.env.example load/env/local.docker.env

# 4. Correr un preset
docker run --rm \
  --env-file load/env/local.docker.env \
  forecast-traffic \
  --config /load/config/normal.conf
```

Para la interfaz web (preset `ui`):

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  -p 8089:8089 \
  forecast-traffic \
  --config /load/config/ui.conf
# Abrir http://127.0.0.1:8089
```

## Ejecución contra AWS

Usá el archivo de entorno para el target remoto:

```bash
cp load/env/aws.env.example load/env/aws.env
# Editá LOCUST_HOST con la IP pública de la EC2

docker run --rm \
  --env-file load/env/aws.env \
  forecast-traffic \
  --config /load/config/intense.conf
```

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `LOCUST_HOST` | Base URL de la API objetivo |
| `API_KEY` | API key válida para requests exitosos |
