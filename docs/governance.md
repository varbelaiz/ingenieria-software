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
desde la raiz del repo despues de cargar datos en bronze:

```bash
uv run --group data dbt source freshness --project-dir data_platform/transform --profiles-dir data_platform/transform
uv run --group data dbt build --project-dir data_platform/transform --profiles-dir data_platform/transform
cp data_platform/transform/target/run_results.json data_platform/transform/target/run_results_build.json
uv run --group data dbt docs generate --project-dir data_platform/transform --profiles-dir data_platform/transform
cp data_platform/transform/target/run_results_build.json data_platform/transform/target/run_results.json
```

`dbt build` deja `run_results.json` con resultados de modelos y tests. Se preserva ese
archivo alrededor de `dbt docs generate` para que DataHub ingiera los resultados del
build, no solamente los de generacion de documentacion. `dbt docs generate` actualiza
`manifest.json` y `catalog.json`, que DataHub usa para modelos, descripciones, columnas,
estadisticas y lineage. `dbt source freshness` genera `sources.json`, que DataHub usa
para poblar freshness y ultima actualizacion desde las fuentes dbt.

## Ejecutar recetas de ingesta

Usar la CLI de DataHub compatible con la version del quickstart (`1.4.0`) desde `uvx`:

```bash
uvx --from "acryl-datahub[postgres,dbt]>=1.4,<1.5" datahub ingest \
  -c data_platform/governance/recipes/postgres.yml --dry-run --no-default-report
uvx --from "acryl-datahub[postgres,dbt]>=1.4,<1.5" datahub ingest \
  -c data_platform/governance/recipes/dbt.yml --dry-run --no-default-report
```

Si los dry-runs terminan sin errores, ejecutar los mismos comandos sin `--dry-run` y sin
`--no-default-report` para publicar metadata en DataHub. La receta de Postgres cataloga
las tablas fisicas del warehouse local; la receta de dbt agrega lineage, descripciones,
freshness y resultados de tests. DataHub recomienda correr ambas para que los nodos dbt
se vinculen con las tablas reales de Postgres.

## Ver lineage y freshness

Para revisar lineage y freshness en la UI, levantar primero los dos stacks locales:

```bash
docker compose -f docker-compose.data.yml up --build
docker compose --env-file .env.datahub -f docker-compose.datahub.yml up -d
```

Generar los artefactos de dbt que DataHub usa para lineage, catalogo, estadisticas,
freshness y resultados de tests:

```bash
uv run --group data dbt source freshness --project-dir data_platform/transform --profiles-dir data_platform/transform
uv run --group data dbt build --project-dir data_platform/transform --profiles-dir data_platform/transform
cp data_platform/transform/target/run_results.json data_platform/transform/target/run_results_build.json
uv run --group data dbt docs generate --project-dir data_platform/transform --profiles-dir data_platform/transform
cp data_platform/transform/target/run_results_build.json data_platform/transform/target/run_results.json
```

Publicar metadata desde la raiz del repo. Correr primero Postgres para catalogar las
tablas fisicas y despues dbt para agregar modelos, descripciones, tests y lineage:

```bash
uvx --from "acryl-datahub[postgres,dbt]>=1.4,<1.5" datahub ingest \
  -c data_platform/governance/recipes/postgres.yml
uvx --from "acryl-datahub[postgres,dbt]>=1.4,<1.5" datahub ingest \
  -c data_platform/governance/recipes/dbt.yml
```

Abrir `http://localhost:9002`, iniciar sesion con `datahub` / `datahub` y buscar datasets
de los esquemas `bronze`, `silver` y `gold`. En una tabla gold como
`gold.fct_produccion`, abrir la vista de lineage y confirmar el recorrido
`bronze.produccion_raw` -> `silver.stg_produccion` -> `gold.fct_produccion`, junto con
las dimensiones gold relacionadas.

Para freshness, revisar la ultima actualizacion y metadata operativa del dataset en
DataHub. Las fuentes bronze declaran `loaded_at_field: _loaded_at` y umbrales de
freshness en `data_platform/transform/models/sources.yml`; los resultados de `dbt build`
se preservan en `target/run_results.json` para que DataHub muestre resultados de tests y
estado reciente del build. Si la UI no muestra datos nuevos, repetir la generacion de
artefactos dbt y las dos ingestas sin `--dry-run`.

## Validacion en CI

CI no instala DataHub como dependencia del proyecto ni levanta el stack de DataHub. El
job `datahub-recipe-validate` genera `sources.json`, `manifest.json`, `catalog.json` y
`run_results.json`; despues usa la CLI de forma efimera con `uvx`:

```bash
uvx --from "acryl-datahub[postgres,dbt]>=1.4,<1.5" datahub ingest \
  -c data_platform/governance/recipes/postgres.yml --dry-run --no-default-report
uvx --from "acryl-datahub[postgres,dbt]>=1.4,<1.5" datahub ingest \
  -c data_platform/governance/recipes/dbt.yml --dry-run --no-default-report
```

El flag `--no-default-report` evita reportar la corrida a DataHub GMS durante la
validacion de CI. Si se necesita validar la publicacion completa de metadata, levantar
DataHub localmente y repetir los comandos sin `--dry-run`.

Dagster no usa una receta pull equivalente. DataHub 1.4.0 documenta la integracion con
Dagster mediante `acryl_datahub_dagster_plugin` y un sensor `datahub_sensor` que emite
metadata despues de cada run. El archivo `data_platform/governance/recipes/dagster.yml`
deja registrada la configuracion local esperada y CI valida su estructura como YAML.
`data_platform.orchestration` registra el sensor automaticamente cuando el plugin
opcional esta instalado; si no esta disponible, Dagster carga las definiciones sin sensor
para mantener liviano el entorno base.

## Detener o reiniciar

Detener los contenedores sin borrar volumenes:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml down
```

Resetear completamente el estado local de DataHub:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml down -v
```
