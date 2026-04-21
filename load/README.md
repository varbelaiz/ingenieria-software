# Synthetic Traffic with Locust

This directory contains the synthetic traffic runner used to populate the
monitoring dashboard and exercise the API without coupling load generation to
the FastAPI runtime. The recommended runtime is a dedicated Docker container
that stays separate from `docker compose up --build`.

## Presets

This runner exposes three presets through native Locust config files:

- `ui`
  - Opens the web UI on `http://127.0.0.1:8089`
  - Intended for manual exploration from the browser
- `normal`
  - Light/normal traffic to populate monitoring and validate the app
- `intense`
  - Moderately aggressive traffic to push the app harder without being a
    destructive stress test by default

All presets share the same traffic model:

- a short deterministic seed at test start so `200`, `403` and `404` series
  appear in monitoring
- then a weighted random mix where successful forecast traffic dominates

## Environment files

Copy the example that matches your target and edit it before running Locust:

- `load/env/local.docker.env.example`
  - Uses `http://host.docker.internal:8000` for a local API started with Docker
- `load/env/aws.env.example`
  - Points to a remote API URL and is intended for a container running near AWS

Documented variables:

- `LOCUST_HOST`
  - Base URL of the API under test
- `API_KEY`
  - Valid API key used for successful requests

## Recommended local workflow

Start the main stack first:

```bash
docker compose up --build
```

Build the standalone Locust image:

```bash
docker build -t forecast-traffic ./load
```

Create a local env file once:

```bash
cp load/env/local.docker.env.example load/env/local.docker.env
```

### UI preset

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  -p 8089:8089 \
  forecast-traffic \
  --config /load/config/ui.conf
```

Open `http://127.0.0.1:8089` in the browser and start the run from the UI.

### `normal` preset

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  forecast-traffic \
  --config /load/config/normal.conf
```

### `intense` preset

```bash
docker run --rm \
  --env-file load/env/local.docker.env \
  forecast-traffic \
  --config /load/config/intense.conf
```

## AWS guidance

Use the same container and presets in both places, but choose the execution
site based on the goal:

- Local laptop:
  - best for smoke tests, demos and manual exploration from the browser
- Container near the API in AWS:
  - better for more representative latency, heavier traffic and private APIs in
    a VPC

To prepare a remote target:

```bash
cp load/env/aws.env.example load/env/aws.env
```

Then run the container wherever it has network access to the API:

```bash
docker run --rm \
  --env-file load/env/aws.env \
  forecast-traffic \
  --config /load/config/intense.conf
```

## Host-local fallback

Docker is the recommended runtime for Locust. If you need to run it directly on
the host, keep the same presets and pass the API host through the shell:

```bash
LOCUST_HOST=http://127.0.0.1:8000 \
API_KEY=api_key \
locust -f load/locustfile.py --config load/config/ui.conf
```
