# API Reference

Base URL: `http://localhost:8000` (local) o `http://<EC2_IP>:8000` (prod).

Documentación interactiva disponible en `/docs`.

## Autenticación

Los endpoints de negocio requieren el header `X-API-Key` con el valor configurado en la variable de entorno `API_KEY`.

```
X-API-Key: <valor de API_KEY>
```

**Rutas que no requieren autenticación:** `/docs`, `/openapi.json`, `/healthz`, `/metrics`.

**Errores de autenticación:**

| Código | Condición | Cuerpo |
|--------|-----------|--------|
| 403 | Header ausente o valor incorrecto | `{"detail": "Invalid or missing API key"}` |
| 500 | Variable `API_KEY` no configurada | `{"detail": "API_KEY is not configured"}` |

---

## GET /api/v1/wells

Devuelve la lista de pozos disponibles para una fecha dada.

**Parámetros de query:**

| Nombre | Tipo | Requerido | Descripción |
|--------|------|-----------|-------------|
| `date_query` | `date` (YYYY-MM-DD) | Sí | Fecha de consulta |

**Respuesta 200:**

```json
{
  "date_query": "2025-02-10",
  "wells": ["POZO-001", "POZO-002", "POZO-003"]
}
```

---

## GET /api/v1/forecast

Devuelve un pronóstico mock de producción con tendencia lineal decreciente para un pozo y rango de fechas.

**Parámetros de query:**

| Nombre | Tipo | Requerido | Descripción |
|--------|------|-----------|-------------|
| `id_well` | `string` | Sí | Identificador del pozo |
| `date_start` | `date` (YYYY-MM-DD) | Sí | Fecha inicial |
| `date_end` | `date` (YYYY-MM-DD) | Sí | Fecha final |

**Pozos válidos:**

| Pozo | Producción base (BOPD) |
|------|------------------------|
| `POZO-001` | 1200.0 |
| `POZO-002` | 980.0 |
| `POZO-003` | 760.0 |

**Algoritmo de pronóstico:**

```
producción(día i) = max(base_value - 7.5 × i, 0)
```

Donde `i` es el índice del día (0 = `date_start`).

**Respuesta 200:**

```json
{
  "id_well": "POZO-001",
  "date_start": "2025-02-10",
  "date_end": "2025-02-12",
  "trend": "linear_decreasing",
  "data": [
    {"date": "2025-02-10", "oil_bopd": 1200.0},
    {"date": "2025-02-11", "oil_bopd": 1192.5},
    {"date": "2025-02-12", "oil_bopd": 1185.0}
  ]
}
```

**Errores:**

| Código | Condición | Cuerpo |
|--------|-----------|--------|
| 404 | `id_well` no existe | `{"detail": "Pozo no encontrado"}` |
| 400 | `date_end` < `date_start` | `{"detail": "date_end debe ser mayor o igual a date_start"}` |

---

## GET /healthz

Health check técnico para probes de infraestructura. No requiere autenticación.

**Respuesta 200:**

```json
{"status": "ok"}
```

---

## GET /metrics

Expone métricas en formato Prometheus. No requiere autenticación.

**Métricas expuestas:**

| Métrica | Tipo | Descripción |
|---------|------|-------------|
| `forecast_api_requests_total` | Counter | Requests totales por `method`, `path`, `status_code` |
| `forecast_api_errors_total` | Counter | Respuestas de error (4xx/5xx) por `method`, `path`, `status_code` |
| `forecast_api_request_duration_seconds` | Histogram | Latencia por request en segundos |
| `process_resident_memory_bytes` | Gauge | Memoria residente del proceso |
| `process_cpu_seconds_total` | Counter | CPU total (usuario + sistema) |
| `process_start_time_seconds` | Gauge | Tiempo de inicio del proceso (epoch Unix) |
