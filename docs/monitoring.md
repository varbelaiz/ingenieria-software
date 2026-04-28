# Monitoreo

El stack de monitoreo está compuesto por Prometheus y Grafana. Corre junto a la API dentro del mismo Docker Compose, tanto en local como en producción.

## Stack

```
API /metrics  ──(scrape 5s)──►  Prometheus :9090  ──(datasource)──►  Grafana :3000
```

## Prometheus

- Configuración en `prometheus/prometheus.yml`
- Intervalo de scrape: **5 segundos**
- Job: `forecast-api` — consume `/metrics` en `api:8000`

## Grafana

- Datasource provisionado automáticamente: `http://prometheus:9090` (UID: `prometheus-fase1`)
- Dashboard provisionado: **"Fase 1 — Technical Monitoring"** (carpeta `Fase 1`)

### Paneles del dashboard

| Panel | Métrica principal | Qué muestra |
|-------|-------------------|-------------|
| Prometheus Scrape Status | `up{job="forecast-api"}` | Si el scrape está activo (Up/Down) |
| Forecast Success Latency P95 | `histogram_quantile(0.95, ...)` | Latencia del percentil 95 en segundos |
| HTTP Error Ratio | `errors / requests` | Proporción de respuestas 4xx/5xx |
| API Request Rate | `rate(forecast_api_requests_total[5m])` | Requests por segundo |
| Forecast Success Latency | P50 / P95 / P99 en serie temporal | Evolución de latencias |
| API Query Frequency by Endpoint | Rate por path | Frecuencia de uso por endpoint |
| HTTP Error Ratio by Status | Rate por código de error | Desglose de errores 4xx/5xx |
| API Process Resource Usage | CPU + memoria del proceso | Consumo de recursos |

## Métricas expuestas por la API

| Métrica | Tipo | Labels |
|---------|------|--------|
| `forecast_api_requests_total` | Counter | `method`, `path`, `status_code` |
| `forecast_api_errors_total` | Counter | `method`, `path`, `status_code` |
| `forecast_api_request_duration_seconds` | Histogram | `method`, `path`, `status_code` |
| `process_resident_memory_bytes` | Gauge | `pid` |
| `process_cpu_seconds_total` | Counter | `pid` |
| `process_start_time_seconds` | Gauge | `pid` |

## Acceso local

- Grafana: `http://localhost:3000`
- Credenciales: `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` del archivo `.env`
- Prometheus: `http://localhost:9090`
