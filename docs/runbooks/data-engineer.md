# Runbook de data engineer

## Reprocesar una particion historica

Este procedimiento reprocesa una particion mensual del pipeline de datos cuando una
fuente historica cambia o cuando se necesita reconstruir un periodo especifico. El flujo
usa el job particionado `end_to_end_data_job`: vuelve a cargar bronze para la particion,
ejecuta `dbt build --select silver gold` y pasa `reprocess_period` a dbt para que
`stg_produccion` y `fct_produccion` refresquen ese periodo.

## Prerrequisitos

- Docker y Docker Compose disponibles.
- Stack de datos levantado:

```bash
docker compose -f docker-compose.data.yml up --build
```

- Warehouse PostgreSQL disponible en el servicio `warehouse`.
- Dagster UI accesible en `http://localhost:3001`.
- Particion mensual elegida con formato `YYYY-MM-01`, por ejemplo `2026-05-01`.

## Ejecutar el reproceso

Reemplazar `2026-05-01` por la particion historica que se quiere reprocesar:

```bash
docker compose -f docker-compose.data.yml run --rm dagster-webserver \
  dagster job execute -w workspace.yaml -j end_to_end_data_job --partition 2026-05-01
```

El job hace tres cosas:

- Re-materializa la particion en `bronze.produccion_raw` y `bronze.pozos_raw`.
- Reemplaza la particion bronze antes de insertar, por lo que re-ejecutar el mismo
  periodo no acumula filas duplicadas.
- Ejecuta `dbt build --select silver gold` con `reprocess_period=2026-05-01`, para que
  los modelos incrementales actualicen `silver.stg_produccion` y `gold.fct_produccion`.

## Verificar que no duplica filas

Antes y despues del reproceso, registrar el conteo de la particion en bronze:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select 'produccion_raw' as table_name, count(*) as rows from bronze.produccion_raw where _load_period = '2026-05-01'
      union all
      select 'pozos_raw' as table_name, count(*) as rows from bronze.pozos_raw where _load_period = '2026-05-01';"
```

Si se corre dos veces la misma particion sin cambios en la fuente, el conteo por tabla
debe quedar igual. Si la fuente cambio, el conteo puede cambiar, pero debe seguir
existiendo una sola version reemplazada para ese `_load_period`.

Verificar tambien que la fact mantiene un unico registro por pozo y periodo:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select id_pozo, periodo, count(*) as rows
      from gold.fct_produccion
      where periodo = date '2026-05-01'
      group by id_pozo, periodo
      having count(*) > 1;"
```

La consulta debe devolver cero filas. Si devuelve resultados, hay duplicacion del grano
`id_pozo` x `periodo` y no se debe usar el resultado para BI hasta corregir el pipeline.

## Revisar el resultado

Confirmar que la particion quedo disponible en la fact:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select periodo, count(*) as rows, max(_loaded_at) as last_loaded_at
      from gold.fct_produccion
      where periodo = date '2026-05-01'
      group by periodo;"
```

Revisar la marca de calidad visible para consumo analitico:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select *
      from gold.quality_marks
      order by checked_at desc
      limit 20;"
```

Si el `dbt build` falla, revisar las filas persistidas por `store_failures`:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select table_name
      from information_schema.tables
      where table_schema = 'dbt_test_failures'
      order by table_name;"
```

Para ver logs, abrir Dagster en `http://localhost:3001`, entrar al run de
`end_to_end_data_job` y revisar el estado de cada step. El run debe terminar en success
antes de considerar terminado el reproceso.
