---
status: Aceptado
date: 2026-04-21
decision-makers: Equipo de Desarrollo
consulted:
informed:
---

# Stack de Monitoreo: Prometheus y Grafana

## Contexto y Declaración del Problema

El proyecto necesita un dashboard técnico para observar latencia, errores y uso básico de recursos durante pruebas locales y despliegues. Necesitamos una forma simple de recolectar y visualizar métricas.

## Impulsores de la Decisión

* Uso de herramientas open source.
* Integración simple con contenedores.
* Visualización rápida de métricas durante demos y pruebas.
* Alineación con el stack de observabilidad visto o incentivado por la cátedra.

## Opciones Consideradas

* Prometheus + Grafana.
* Datadog (SaaS).
* CloudWatch / Stackdriver (Dependientes de proveedor Cloud).

## Resultado de la Decisión

Opción elegida: "Prometheus + Grafana", porque permiten recolectar y visualizar métricas con contenedores y sin depender de un servicio SaaS. También son las herramientas de observabilidad trabajadas en el contexto de la materia. Para el alcance actual alcanza con un stack autogestionado y fácil de levantar con Docker Compose.

### Consecuencias

* Bueno, porque son herramientas conocidas y bien soportadas.
* Bueno, porque el dashboard se puede versionar junto con el proyecto.
* Malo, porque añade sobrecarga al mantener más contenedores en el ambiente de desarrollo.

### Confirmación

Confirmado en el repositorio: `docker-compose.yml` define servicios `prometheus` y `grafana`, y existen archivos de provisioning y dashboards bajo `grafana/` y `prometheus/`.
