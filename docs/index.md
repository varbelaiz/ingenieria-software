# Documentación — Plataforma Predictiva de Producción de Hidrocarburos

## Índice

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](architecture.md) | Visión general del sistema, componentes y flujo de un request |
| [API Reference](api-reference.md) | Endpoints, autenticación, parámetros y respuestas |
| [Infraestructura](infrastructure.md) | Recursos AWS, ambientes (staging/prod) e IaC con Terraform |
| [Monitoreo](monitoring.md) | Stack Prometheus + Grafana, métricas y dashboard |
| [Load Testing](load-testing.md) | Tráfico sintético con Locust, presets y ejecución |
| [Ops](ops.md) | Deploy, secretos y monitoreo operativo en alto nivel |
| [Runbook de Data Engineer](runbooks/data-engineer.md) | Reproceso histórico de particiones, verificación de idempotencia y revisión de resultados |
