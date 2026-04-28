---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Modelo Pull de Recolección de Métricas Telemétricas

## Contexto y Declaración del Problema

Habiendo elegido Prometheus, debemos definir cómo se exponen las métricas de la API. La alternativa es que la aplicación empuje datos a un servicio externo o que Prometheus consulte periódicamente un endpoint de métricas.

## Impulsores de la Decisión

* Impacto en el rendimiento del request del usuario.
* Resiliencia del sistema (qué pasa si el servidor de métricas no está disponible).

## Opciones Consideradas

* Modelo Push (ej. enviar a InfluxDB o StatsD en cada request).
* Modelo Pull (Prometheus hace un scrapeo periódico de un endpoint `/metrics`).

## Resultado de la Decisión

Opción elegida: "Modelo Pull", porque desacopla los endpoints de negocio del proceso de recolección. La API actualiza métricas en memoria y expone `/metrics`; Prometheus las consulta periódicamente.

### Consecuencias

* Bueno, porque la API no se bloquea si el sistema de monitoreo se cae o satura.
* Bueno, porque no requiere credenciales ni llamadas salientes desde la API hacia el sistema de monitoreo.
* Malo, porque las métricas en memoria se pierden al reiniciar el proceso de la API.
* Malo, porque no se guardan eventos individuales, solo series agregadas.

### Confirmación

Confirmado en el repositorio: `app/monitoring.py` expone `/metrics` en formato compatible con Prometheus y `prometheus/prometheus.yml` scrapea a la API.
