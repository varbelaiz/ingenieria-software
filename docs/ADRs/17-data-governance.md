# ADR-17: Plataforma de gobierno de datos

```
status: Aceptado
date: 2026-06-14
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La Fase 2 necesita una plataforma de gobierno que permita descubrir los datos del
warehouse, revisar la ultima actualizacion de las tablas y navegar el lineage a nivel
tabla. Tambien debe integrarse con el stack ya elegido: dbt para transformaciones,
PostgreSQL como warehouse y Dagster como orquestador.

La consigna menciona DataHub como herramienta vista en clase, pero admite alternativas
si se justifican. La decision debe balancear cobertura funcional, costo operativo local
y riesgo de soporte para el equipo.

## Impulsores de la decision

* Lineage navegable a nivel tabla desde bronze hasta gold.
* Visibilidad de freshness o ultima actualizacion de los datasets.
* Ingesta de metadata desde dbt, PostgreSQL y Dagster.
* Operacion local con Docker Compose, sin requerir infraestructura cloud adicional.
* Menor riesgo de soporte usando una herramienta vista en clase.

## Opciones consideradas

* **DataHub** - catalogo de datos open source con conectores para dbt, Postgres y
  Dagster, UI de lineage y soporte para metadata operativa.
* **OpenMetadata** - catalogo open source con buena experiencia de usuario, conectores
  amplios y foco fuerte en discovery y calidad.
* **Amundsen** - catalogo open source liviano, orientado principalmente a busqueda y
  descubrimiento de datasets.

## Resultado de la decision

Opcion elegida: **DataHub**.

DataHub cubre los requisitos centrales con menos riesgo para este proyecto: ingiere los
artefactos de dbt (`manifest.json`, `catalog.json` y `run_results.json`) para exponer
modelos, descripciones, resultados de tests y lineage; ingiere PostgreSQL para vincular
los nodos logicos de dbt con las tablas fisicas del warehouse; y documenta integracion
con Dagster mediante `acryl_datahub_dagster_plugin` y `datahub_sensor` para emitir
metadata de workflows y materializaciones.

OpenMetadata tambien seria una alternativa valida para gobierno y discovery, pero no fue
la herramienta usada en la cursada y agregaria incertidumbre de setup y soporte. Amundsen
es mas liviano, aunque su foco esta mas en discovery que en lineage/freshness operacional
de punta a punta. Para el alcance de Fase 2, DataHub maximiza alineacion con la consigna,
conectores disponibles y evidencia navegable en una sola UI.

## Consecuencias

**Pros**

* DataHub permite navegar lineage bronze -> silver -> gold desde la UI.
* Las recetas de dbt y Postgres publican metadata del warehouse y resultados
  de calidad sin cambiar el pipeline principal.
* La herramienta esta alineada con la cursada y reduce riesgo de soporte.

**Cons**

* El quickstart de DataHub es pesado: levanta Kafka, OpenSearch, MySQL y
  servicios propios.
* Corre en un Compose separado y local; no entra en la instancia AWS
  `t3.micro` de Fase 1.
* La metadata no aparece sola: hay que generar artefactos dbt y ejecutar las
  recetas de ingesta para refrescar DataHub.

## Confirmacion

Confirmado en `docker-compose.datahub.yml`, `.env.datahub.example` y
`data_platform/governance/recipes/`. Las instrucciones operativas quedan en
`docs/governance.md`: levantar DataHub, generar artefactos dbt, ejecutar ingestas y
verificar lineage/freshness desde la UI.
