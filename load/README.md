# Load Testing

La documentación completa de tráfico sintético con Locust está en [`docs/load-testing.md`](../docs/load-testing.md).

## Referencia rápida

```bash
# Construir imagen
docker build -t forecast-traffic ./load

# Preset normal (headless)
docker run --rm --env-file load/env/local.docker.env forecast-traffic --config /load/config/normal.conf

# Preset UI (interfaz web en :8089)
docker run --rm --env-file load/env/local.docker.env -p 8089:8089 forecast-traffic --config /load/config/ui.conf

# Preset intense
docker run --rm --env-file load/env/local.docker.env forecast-traffic --config /load/config/intense.conf
```
