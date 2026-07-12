# Documentación — Plataforma Predictiva de Producción de Hidrocarburos

## Índice

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](architecture.md) | Visión general del sistema, componentes y flujo de un request |
| [API Reference](api-reference.md) | Endpoints, autenticación, parámetros y respuestas |
| [Plataforma de datos](data-platform.md) | Arquitectura medallion end-to-end: extracción, Dagster, dbt, calidad, gobierno y BI |
| [Modelo de datos](data-model.md) | Modelo estrella gold: grano, fact, dimensiones, surrogate keys y estrategia SCD |
| [Infraestructura](infrastructure.md) | Recursos AWS, ambientes (staging/prod) e IaC con Terraform |
| [Monitoreo](monitoring.md) | Stack Prometheus + Grafana, métricas y dashboard |
| [Load Testing](load-testing.md) | Tráfico sintético con Locust, presets y ejecución |
| [Gobierno de datos](governance.md) | Quickstart local de DataHub para catalogo y gobierno |
| [Ops](ops.md) | Deploy, secretos y monitoreo operativo en alto nivel |
| [Plan Fase 3](planes/fase-3.md) | Plan vivo de PRs, ADRs y handoff para ML Engineering |
| [Guion del video Fase 3](fase-3-video.md) | Qué mostrar y qué decir en la demo de ML Engineering, con comandos exactos |
| [Runbook de Data Engineer](runbooks/data-engineer.md) | Reproceso histórico de particiones, verificación de idempotencia y revisión de resultados |
| [Runbook de BI User](runbooks/bi-user.md) | Validar frescura y calidad (quality_marks + DataHub) antes de publicar un reporte |
| [Runbook de ML Engineer](runbooks/ml-engineer.md) | Materializar features, entrenar, ver runs en MLflow, promover el modelo, llamar la API y disparar retrain |
