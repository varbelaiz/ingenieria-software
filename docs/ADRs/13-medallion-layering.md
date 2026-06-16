# ADR-13: Capas medallion para la plataforma de datos

```
status: Aceptado
date: 2026-06-09
decision-makers: Equipo de Desarrollo
```

## Contexto y declaración del problema

La Fase 2 necesita ordenar el flujo de datos reales de producción de hidrocarburos desde
datos.gob.ar hasta modelos consumibles por BI y gobierno. La decisión central es dónde
preservar datos crudos, dónde limpiar/tipar y dónde publicar entidades analíticas.

## Impulsores de la decisión

* Mantener trazabilidad hacia los CSV oficiales.
* Permitir reprocesos idempotentes por período de carga.
* Separar ingestión cruda de reglas de negocio.
* Facilitar tests de calidad y lineage con dbt.

## Opciones consideradas

* **Una sola capa transformada** — cargar directo a tablas analíticas.
* **Dos capas raw + curated** — preservar crudo y publicar modelos limpios.
* **Medallion bronze/silver/gold** — raw, staging conformado y modelo dimensional.

## Resultado de la decisión

Opción elegida: **medallion bronze/silver/gold**.

La capa **bronze** conserva todas las columnas de los CSV como texto y agrega solo
metadata técnica de carga: `_load_period`, `_loaded_at`, `_source_url`, `_resource_id` y
`_row_hash`. No castea fechas, números ni categorías de negocio. La capa **silver** queda
responsable de tipar, limpiar, deduplicar y conformar datos. La capa **gold** queda
responsable del modelo estrella y las métricas consumibles.

## Consecuencias

* Bueno, porque un cambio en reglas de negocio se resuelve reprocesando silver/gold sin
  volver a descargar la fuente.
* Bueno, porque bronze permite auditar qué recurso y período de carga produjo cada fila.
* Bueno, porque dbt puede declarar fuentes sobre bronze y exponer freshness desde
  `_loaded_at`.
* Malo, porque bronze no es cómodo para análisis directo: todo llega como texto.

## Confirmación

Confirmado en `data_platform/extraction/bronze_loader.py`: la carga crea tablas en el
schema `bronze`, reemplaza idempotentemente por `_load_period` y agrega metadata técnica.
Confirmado en `data_platform/transform/models/sources.yml`: dbt declara
`bronze.produccion_raw` y `bronze.pozos_raw` con `loaded_at_field: _loaded_at`.
