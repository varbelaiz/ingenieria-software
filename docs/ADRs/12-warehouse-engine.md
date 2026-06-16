# ADR-12: Motor del warehouse

```
status: Aceptado
date: 2026-06-04
decision-makers: Equipo de Desarrollo
```

## Contexto y declaración del problema

Hay que elegir el motor donde viven las capas medallion (bronze/silver/gold) y el modelo
estrella, que además sirve a Metabase (BI) y a DataHub (gobierno) de forma concurrente.

## Impulsores de la decisión

* Soporte multiusuario concurrente (dbt, Metabase, DataHub, Dagster).
* Conectores nativos en todo el stack elegido.
* Compatibilidad con dbt-postgres y dbt incremental/merge.
* Operación local via Docker Compose sin costo cloud.

## Opciones consideradas

* **PostgreSQL** — relacional, multiusuario, conectores nativos en Metabase y DataHub.
* **DuckDB** — analítico embebido, rapidísimo en dev, archivo único.
* **BigQuery / Snowflake** — warehouses cloud gestionados.

## Resultado de la decisión

Opción elegida: **PostgreSQL 16**.

DuckDB es ideal para el loop de desarrollo de dbt, pero es **single-writer embebido**: no
encaja bien como warehouse servido simultáneamente a Metabase, DataHub y el orquestador
(bloqueos de escritura concurrente). BigQuery/Snowflake son excelentes pero implican
cuenta cloud y costo, innecesarios para el alcance del proyecto. Postgres da concurrencia
multiusuario real, tiene adaptadores nativos en dbt (`dbt-postgres`), Metabase y DataHub,
y corre en el mismo Compose en el puerto 5433 (no colisiona con instancias locales).

## Consecuencias

* Bueno, porque es multiusuario y tiene conectores nativos en todo el stack.
* Bueno, porque corre local en Compose sin costo cloud.
* Bueno, porque `dbt-postgres` soporta `incremental_strategy='merge'` (requisito del ADR-14).
* Malo, porque no es columnar: en volúmenes mucho mayores rendiría peor que un warehouse
  analítico dedicado (no es el caso a este volumen).

## Confirmación

Confirmado en `docker-compose.data.yml`: servicio `warehouse` (postgres:16, puerto 5433)
y en `data_platform/transform/profiles.yml`: target postgres apuntando al warehouse.
