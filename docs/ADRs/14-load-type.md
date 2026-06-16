# ADR-14: Tipo de carga (full vs incremental vs merge/upsert)

```
status: Aceptado
date: 2026-06-10
decision-makers: Equipo de Desarrollo
```

## Contexto y declaración del problema

La consigna pide definir y justificar explícitamente el tipo de carga, y que sea posible
reprocesar los datos de una fecha si hay cambios. El dataset de producción de datos.gob.ar
se **revisa y corrige retroactivamente**: los volúmenes de meses pasados pueden cambiar en
publicaciones posteriores. La capa bronze ya particiona por `_load_period`, de modo que un
mismo `(pozo, período)` corregido aparece en más de una carga; la decisión es cómo
materializa silver (y luego la fact gold) ese flujo.

## Impulsores de la decisión

* El dato histórico puede cambiar entre publicaciones.
* Debe poder reprocesarse una fecha puntual sin recargar todo.
* El procesamiento debe ser idempotente.
* Costo/tiempo de procesamiento acotado a medida que crece la serie.

## Opciones consideradas

* **Full load** — borrar y recargar todo en cada corrida.
* **Incremental append** — agregar solo filas nuevas.
* **Incremental merge / upsert** — insertar nuevas y actualizar las que cambiaron, por clave.

## Resultado de la decisión

Opción elegida: **incremental merge / upsert** sobre los staging de producción y la fact.

Full load es el más simple y trivialmente idempotente, pero recargar todo el histórico en
cada corrida no escala en tiempo a medida que crece la serie y desperdicia cómputo. Append
es barato pero **incorrecto** para este dataset: si un mes pasado se corrige, append
duplicaría el período en vez de actualizarlo. Merge/upsert con `unique_key` por
`(id_pozo, periodo)` actualiza el período corregido y agrega los nuevos, que es exactamente
el comportamiento que pide un dataset con correcciones retroactivas. Además es idempotente:
re-correr una partición converge al mismo estado.

El reproceso de una fecha puntual se expone con la variable `reprocess_period`
(`dbt run --select stg_produccion --vars 'reprocess_period: 2016-01-01'`), que reincorpora
ese período al filtro incremental aunque su `_loaded_at` ya no sea el más reciente.

`stg_pozos` queda fuera de esta estrategia: es un listado de referencia sin grano temporal,
así que se materializa como tabla deduplicada al registro más reciente por pozo.

## Consecuencias

* Bueno, porque refleja correctamente las correcciones retroactivas de la fuente.
* Bueno, porque permite reprocesar una fecha puntual (re-merge de esa partición).
* Bueno, porque es idempotente por construcción.
* Malo, porque el merge es más complejo que append y requiere una `unique_key` confiable.
* Malo, porque un cambio de esquema en la fuente exige revisar la lógica de merge.

## Confirmación

Confirmado en `data_platform/transform/models/silver/stg_produccion.sql`:
`materialized='incremental'`, `incremental_strategy='merge'` y `unique_key=['id_pozo',
'periodo']`, con filtro incremental por `_loaded_at` y override `reprocess_period`. La fact
`fct_produccion` (PR posterior) hereda esta decisión.
