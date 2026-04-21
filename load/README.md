# Tráfico Sintético con Locust

Este directorio contiene el runner de tráfico sintético usado para poblar el
dashboard de monitoreo y exigir la API sin acoplar la generación de carga al
runtime de FastAPI.

La forma recomendada de uso es un contenedor Docker separado del stack
principal. Por diseño, Locust no forma parte de `docker compose up --build`.

## Qué hay en este directorio

- `load/locustfile.py`: define el comportamiento del tráfico.
- `load/traffic_config.py`: helpers de configuración compartidos.
- `load/config/`: presets nativos de Locust (`ui`, `normal`, `intense`).
- `load/env/`: archivos de ejemplo para targets locales y remotos.

## Variables y archivos de entorno

Copiá el ejemplo que corresponda a tu escenario antes de ejecutar Locust:

- `load/env/local.docker.env.example`: pensado para una API local levantada con Docker en `http://host.docker.internal:8000`.
- `load/env/aws.env.example`: pensado para una API remota o desplegada cerca de AWS.

Variables documentadas:

- `LOCUST_HOST`: base URL de la API objetivo.
- `API_KEY`: API key válida para requests exitosos.

## Workflow local recomendado

1. Levantar primero el stack principal:

```bash
docker compose up --build
```

2. Construir la imagen de Locust:

```bash
docker build -t forecast-traffic ./load
```

3. Crear el archivo de entorno local una única vez:

```bash
cp load/env/local.docker.env.example load/env/local.docker.env
```

4. Ejecutar uno de los presets disponibles.

## Presets disponibles

Todos los presets comparten el mismo modelo de tráfico:

- una siembra corta al inicio para forzar respuestas `200`, `403` y `404`
- luego un mix ponderado donde predominan las requests exitosas a `forecast`

### Preset `ui`

Abre la interfaz web de Locust para exploración manual desde el navegador.

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

Genera tráfico liviano para poblar el monitoreo y validar comportamiento base.

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  forecast-traffic \
  --config /load/config/normal.conf
```

### Preset `intense`

Genera tráfico más agresivo para exigir más a la aplicación sin convertirlo,
por defecto, en una prueba destructiva.

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  forecast-traffic \
  --config /load/config/intense.conf
```

## Cuándo correr Locust cerca de AWS

Ejecutarlo localmente está bien para:

- smoke tests
- demos
- exploración manual de la UI
- poblar el dashboard de monitoreo rápidamente

Si la API corre en AWS, conviene ejecutar el contenedor de Locust cerca del
servicio cuando quieras:

- latencia más representativa
- mayor capacidad de carga
- acceso a APIs privadas dentro de una VPC

Preparación del target remoto:

```bash
cp load/env/aws.env.example load/env/aws.env
```

Ejemplo de ejecución:

```bash
docker run --rm \
  --env-file load/env/aws.env \
  forecast-traffic \
  --config /load/config/intense.conf
```

## Alternativa host-local sin Docker

Docker es el runtime recomendado. Si necesitás correr Locust directamente desde
el host, podés usar la instalación del proyecto y mantener los mismos presets:

```bash
LOCUST_HOST=http://127.0.0.1:8000 \
API_KEY=api_key \
uv run locust -f load/locustfile.py --config load/config/ui.conf
```
