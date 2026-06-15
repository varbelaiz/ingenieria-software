# ADR-15: Calidad de datos persistida en gold con dbt

```
status: Aceptado
date: 2026-06-12
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La Fase 2 ya publica datos en silver y gold con un modelo estrella, pero todavia
faltaba una puerta operativa de calidad que fuera persistida, visible y bloqueante.
El equipo necesita detectar fallas de completitud, validez, relaciones y grano antes
de promover datos aguas abajo, y al mismo tiempo dejar evidencia consultable para BI
y gobierno.

## Impulsores de la decision

* Reutilizar el stack ya elegido alrededor de dbt.
* Hacer que una falla de calidad frene la promocion de silver/gold.
* Persistir filas invalidas para investigacion posterior.
* Exponer un resumen simple de estado para consumo analitico.
* Evitar sumar otra plataforma operativa en este PR.

## Opciones consideradas

* **dbt tests + dbt-expectations** - tests declarativos sobre modelos, soporte para
  `store_failures` y ejecucion integrada con `dbt build`.
* **Great Expectations** - framework dedicado con expectativas ricas y data docs.
* **Soda** - enfoque centrado en data quality scans y alertas operativas.

## Resultado de la decision

Opcion elegida: **dbt tests + dbt-expectations**.

Great Expectations y Soda ofrecen capacidades potentes, especialmente para catalogos
de reglas mas amplios y observabilidad dedicada. El costo en este contexto es agregar
otra superficie operativa, otra sintaxis de reglas y otro punto de integracion para un
pipeline que ya modela contratos de datos en dbt. Como silver y gold ya viven en dbt,
la opcion mas directa es expresar la calidad junto a los modelos, correrla dentro de
`dbt build` y persistir los errores con `store_failures`.

La implementacion adoptada combina tres piezas:

* `dbt build --select silver gold` como gate bloqueante de promocion.
* `store_failures` en el esquema `dbt_test_failures` para conservar filas invalidas.
* `gold.quality_marks` como vista resumida visible para BI y gobierno.

## Consecuencias

* Bueno, porque la calidad queda versionada junto a los modelos gold.
* Bueno, porque un test fallido rompe el build y evita promociones incorrectas.
* Bueno, porque las fallas quedan persistidas en `dbt_test_failures`.
* Bueno, porque `gold.quality_marks` da una marca visible y consultable del estado.
* Malo, porque la cobertura operativa queda limitada a lo que expresemos en dbt/SQL.
* Malo, porque alertas, retries, schedules y backfills completos quedan para PR6.

## Confirmacion

Confirmado en `data_platform/transform/`: tests declarativos ampliados, `store_failures`
habilitado y vista `gold.quality_marks`. Confirmado en `data_platform/orchestration/`:
job Dagster `data_quality_job` que ejecuta `dbt build` y falla ante un exit code no cero.
