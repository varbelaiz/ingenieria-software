# ADR-21: Feature store persistido para entrenamiento e inferencia

```
status: Propuesto
date: 2026-06-25
decision-makers: Equipo de Desarrollo
```

## Contexto y declaracion del problema

La Fase 3 exige que el procesamiento y generacion de features quede persistido en un
feature store usado durante la inferencia. El sistema ya cuenta con warehouse PostgreSQL,
modelos dbt en silver/gold y orquestacion Dagster. La decision debe evitar que training e
inferencia calculen features por caminos distintos, porque eso produciria training-serving
skew.

## Impulsores de la decision

* Persistir features, no solo construirlas en memoria durante el entrenamiento.
* Consultar las mismas features desde training y desde la API.
* Reprocesar features para un `as_of_date` dado.
* Evitar leakage temporal usando solo informacion disponible hasta la fecha de corte.
* Reutilizar Postgres, dbt y Dagster ya presentes en la plataforma de datos.

## Opciones consideradas

* **Postgres como feature store** - esquema o modelos dedicados de features dentro del
  warehouse, materializados por dbt/Dagster y consultados por Python.
* **Feast** - feature store dedicado con abstracciones offline/online, historizacion y
  serving, pero con mayor complejidad operativa.
* **Parquet versionado** - archivos particionados por fecha, simples para entrenamiento
  batch, pero incomodos para lookup online desde la API.

## Resultado de la decision

Opcion propuesta: **Postgres como feature store persistido**.

Postgres ya es el motor elegido para la plataforma de datos en ADR-12 y ya se conecta con
dbt, Dagster y la API. Para el alcance de la materia, un esquema `ml_features` con tablas
o vistas materializadas por fecha cubre persistencia, reproducibilidad y lookup desde
inferencia sin introducir una herramienta nueva. Feast es conceptualmente mas completo,
pero su valor aparece cuando existen multiples fuentes, store online separado, equipos
grandes o necesidades de baja latencia mas estrictas. Parquet es atractivo para batch,
pero obliga a resolver de nuevo el serving desde la API.

## Consecuencias

**Pros**

* Reusa el warehouse y las credenciales ya documentadas.
* Permite materializar y validar features con dbt/Dagster.
* Simplifica la demo: se pueden inspeccionar las features con SQL.
* Evita una plataforma adicional para la entrega local.

**Cons**

* No provee abstracciones nativas de feature registry como Feast.
* Para escala o baja latencia real podria requerir un store online separado.
* El equipo debe definir convenciones propias para nombres, granularidad y freshness.

## Confirmacion esperada

Confirmar en PR 2 con modelos/tablas persistidas bajo `ml_features`, codigo de lectura en
`ml/features/store.py`, tests de idempotencia, lookup por fecha y ausencia de leakage
temporal.

