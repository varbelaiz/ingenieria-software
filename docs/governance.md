# Gobierno de datos

La plataforma usa DataHub como catalogo local para gobierno de datos. Este primer
quickstart levanta solamente la UI y los servicios base de DataHub; las recetas de
ingesta de dbt, Postgres y Dagster se agregan en el siguiente commit de PR7.

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
`http://localhost:3001`. Las recetas de ingesta que conectan DataHub con dbt, Postgres y
Dagster quedan fuera de este primer commit.

## Detener o reiniciar

Detener los contenedores sin borrar volumenes:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml down
```

Resetear completamente el estado local de DataHub:

```bash
docker compose --env-file .env.datahub -f docker-compose.datahub.yml down -v
```
