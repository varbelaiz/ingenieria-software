# Synthetic Traffic with k6

This directory contains a minimal `k6` traffic generator that is intentionally
kept separate from the API runtime.

## Environment variables

- `API_BASE_URL`
  - Default: `http://127.0.0.1:8000`
- `API_KEY`
  - Default: `api_key`
- `TRAFFIC_PROFILE`
  - Supported values:
    - `seed`
    - `realistic`
  - Default: `seed`

## Local usage

Run the API first, ideally with the existing Docker Compose stack.

### Seed profile

This profile is deterministic and guarantees `200`, `403`, and `404` traffic to
keep the dashboard panels populated.

```bash
API_BASE_URL=http://127.0.0.1:8000 \
API_KEY=api_key \
TRAFFIC_PROFILE=seed \
k6 run load/traffic.js
```

### Realistic profile

This profile uses a weighted mix where successful forecast traffic dominates,
with smaller proportions of wells traffic and controlled `403` / `404` errors.

```bash
API_BASE_URL=http://127.0.0.1:8000 \
API_KEY=api_key \
TRAFFIC_PROFILE=realistic \
k6 run load/traffic.js
```

## Dockerized usage

Build the traffic generator image:

```bash
docker build -t forecast-traffic ./load
```

Run it against a local API:

```bash
docker run --rm \
  -e API_BASE_URL=http://host.docker.internal:8000 \
  -e API_KEY=api_key \
  -e TRAFFIC_PROFILE=seed \
  forecast-traffic
```

Run it against a remote API:

```bash
docker run --rm \
  -e API_BASE_URL=https://your-api.example.com \
  -e API_KEY=your_api_key \
  -e TRAFFIC_PROFILE=realistic \
  forecast-traffic
```

This setup is intentionally portable so it can later run as a containerized job
outside the API service, including on cloud infrastructure.
