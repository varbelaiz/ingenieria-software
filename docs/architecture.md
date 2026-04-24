# Arquitectura

## Qué resuelve

La plataforma expone una API REST para consultar pozos de hidrocarburos disponibles y generar pronósticos mock de producción. Incluye un stack de monitoreo técnico (Prometheus + Grafana) y un runner de tráfico sintético (Locust) para validar el comportamiento bajo carga.

## Diagrama de componentes

```
                        ┌─────────────────────────────────────────┐
                        │              AWS EC2 Instance            │
                        │                                         │
  Cliente / Locust ────►│  FastAPI :8000                          │
                        │      │                                  │
                        │      │ /metrics (scrape cada 5s)        │
                        │      ▼                                  │
                        │  Prometheus :9090                       │
                        │      │                                  │
                        │      │ datasource                       │
                        │      ▼                                  │
                        │  Grafana :3000                          │
                        └─────────────────────────────────────────┘

  GitHub Actions ──────► ECR (imagen Docker) ────► EC2 (deploy vía SSM)
```

## Stack tecnológico

| Tecnología | Rol |
|-----------|-----|
| **FastAPI** | Framework HTTP — tipado, validación automática, OpenAPI generado |
| **Uvicorn** | ASGI server de producción |
| **Python 3.10+** | Lenguaje principal |
| **uv** | Gestión de dependencias y entorno virtual |
| **Docker + Compose** | Empaquetado y orquestación local/prod |
| **Prometheus** | Recolección de métricas de la API |
| **Grafana** | Visualización de métricas en tiempo real |
| **Locust** | Tráfico sintético para stress testing y poblado del dashboard |
| **Terraform** | Infraestructura como código (IaC) en AWS |
| **GitHub Actions** | CI (lint + tests) y CD (build + deploy) |

## Estructura de módulos (`app/`)

```
app/
├── main.py         # Punto de entrada: instancia FastAPI, registra routers y middleware
├── middleware.py   # Validación de API key + instrumentación de métricas por request
├── health.py       # Endpoint /healthz para probes de infraestructura
├── monitoring.py   # Métricas Prometheus y endpoint /metrics
├── wells/
│   └── routes.py   # GET /api/v1/wells — lista de pozos para una fecha
└── forecast/
    └── routes.py   # GET /api/v1/forecast — pronóstico de producción para un pozo
```

## Flujo de un request

```
Cliente
  │
  │  GET /api/v1/forecast?id_well=POZO-001&...
  │  X-API-Key: <api_key>
  ▼
ApiKeyMiddleware
  ├─ ¿ruta excluida? (/docs, /metrics, /healthz) → pasa directo
  ├─ ¿API_KEY configurada? → sino, 500
  ├─ ¿header X-API-Key válido? → sino, 403
  └─ llama al endpoint
        │
        ▼
  ForecastRouter
  ├─ valida id_well (POZO-001/002/003) → sino, 404
  ├─ valida date_end >= date_start → sino, 400
  └─ calcula pronóstico lineal → 200 JSON
        │
        ▼
  ApiKeyMiddleware (post-response)
  └─ registra métricas (duración, status code, errores)
```
