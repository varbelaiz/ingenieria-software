---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Uso de Locust para Tráfico Sintético y Pruebas de Carga

## Contexto y Declaración del Problema

El proyecto necesita generar tráfico contra la API para validar comportamiento básico bajo carga y, al mismo tiempo, poblar las métricas que consume el dashboard de Prometheus y Grafana. Se debe elegir una herramienta para definir escenarios repetibles y ejecutarlos localmente o contra el despliegue en AWS.

## Impulsores de la Decisión

* Poder simular usuarios concurrentes haciendo requests HTTP.
* Definir escenarios de tráfico versionados junto con el código.
* Ejecutar pruebas en modo headless y, cuando haga falta, con interfaz web.
* Alineación con Locust como herramienta vista o incentivada por la cátedra.

## Opciones Consideradas

* Locust.
* k6.
* Apache JMeter.
* Scripts propios con `httpx` o `curl`.

## Resultado de la Decisión

Opción elegida: "Locust", porque permite modelar usuarios y escenarios HTTP en Python, correr presets headless o con UI, y reutilizar conocimientos del stack principal del proyecto. Además, estaba alineado con las herramientas trabajadas en el contexto de la materia.

### Consecuencias

**Pros**

* Los escenarios quedan expresados como código Python en `load/`.
* Los presets facilitan correr carga normal, intensa o con UI.
* El tráfico sintético ayuda a visualizar métricas reales en Grafana.

**Cons**

* Agrega otra imagen/configuración Docker a mantener.
* Los resultados dependen del entorno desde donde se ejecuta la carga.

### Confirmación

Confirmado en el repositorio: `load/locustfile.py` define usuarios y escenarios de tráfico, `load/config/` contiene presets de ejecución y `docs/load-testing.md` documenta cómo correr Locust localmente o contra AWS.
