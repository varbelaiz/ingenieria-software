# Gobierno de datos

La plataforma usa DataHub como catalogo local para gobierno de datos. El quickstart
levanta la UI y los servicios base de DataHub; las recetas locales de ingesta de dbt y
Postgres viven en `data_platform/governance/recipes/`. Dagster se integra con DataHub
mediante sensor/plugin, documentado en `data_platform/governance/recipes/dagster.yml`.

## Prerrequisitos

- Docker y Docker Compose v2.
- Recursos suficientes asignados a Docker. DataHub recomienda al menos 2 CPUs, 8 GB de
  RAM, 2 GB de swap y espacio local para volumenes.

Este stack es solo para desarrollo local. No esta pensado para produccion ni para la
instancia AWS `t3.micro` de Fase 1.

## Levantar DataHub

Crear el archivo local de variables:

```bash
cp .env.datahub.example .env.datahub
```

Reemplazar en `.env.datahub` los valores de `DATAHUB_TOKEN_SERVICE_SIGNING_KEY` y
`DATAHUB_TOKEN_SERVICE_SALT`. Se puede generar cada valor con:

```bash
openssl rand -base64 32
```

Levantar el stack:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml up -d
```

## Acceso local

La UI queda disponible en:

```text
http://localhost:9002
```

Credenciales locales del quickstart:

```text
usuario: datahub
password: datahub
```

El puerto de la UI se puede cambiar en `.env.datahub` con `DATAHUB_FRONTEND_PORT`.

## Relacion con el stack de datos

DataHub corre en un Compose separado porque arrastra servicios pesados como Kafka,
OpenSearch y MySQL. Para tener datos reales que catalogar, levantar tambien el stack de
datos existente:

```bash
docker compose -f docker-compose.data.yml up --build
```

Ese stack publica el warehouse PostgreSQL en `localhost:5433` y Dagster en
`http://localhost:3001`.

## Generar artefactos dbt

La receta de dbt lee los artefactos de `data_platform/transform/target/`. Generarlos
despues de cargar datos en bronze:

```bash
cd data_platform/transform
dbt build --profiles-dir .
cp target/run_results.json target/run_results_build.json
dbt docs generate --profiles-dir .
cp target/run_results_build.json target/run_results.json
```

`dbt build` deja `run_results.json` con resultados de modelos y tests. Se preserva ese
archivo alrededor de `dbt docs generate` para que DataHub ingiera los resultados del
build, no solamente los de generacion de documentacion. `dbt docs generate` actualiza
`manifest.json` y `catalog.json`, que DataHub usa para modelos, descripciones, columnas,
estadisticas y lineage.

## Ejecutar recetas de ingesta

Instalar o usar la CLI de DataHub compatible con la version del quickstart (`1.4.0`) y
correr las recetas desde la raiz del repo:

```bash
datahub ingest -c data_platform/governance/recipes/postgres.yml --dry-run
datahub ingest -c data_platform/governance/recipes/dbt.yml --dry-run
```

Si los dry-runs terminan sin errores, ejecutar los mismos comandos sin `--dry-run` para
publicar metadata en DataHub. La receta de Postgres cataloga las tablas fisicas del
warehouse local; la receta de dbt agrega lineage, descripciones y resultados de tests.
DataHub recomienda correr ambas para que los nodos dbt se vinculen con las tablas reales
de Postgres.

Dagster no usa una receta pull equivalente. DataHub 1.4.0 documenta la integracion con
Dagster mediante `acryl_datahub_dagster_plugin` y un sensor `datahub_sensor` que emite
metadata despues de cada run. El archivo `data_platform/governance/recipes/dagster.yml`
deja registrada la configuracion local esperada; la validacion completa queda para el
commit que agregue el sensor a `data_platform/orchestration/`.

## Detener o reiniciar

Detener los contenedores sin borrar volumenes:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml down
```

Resetear completamente el estado local de DataHub:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml down -v
```
