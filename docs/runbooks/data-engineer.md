# Runbook de data engineer

**Role:** Data Engineer
**Responsibilities:** Pipeline operation, partition backfills, incident response for extraction and transformation failures.
**Owner:** Data Engineering team.

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

## Manejo de fallos

### dbt build falla

1. Abrir Dagster UI en `http://localhost:3001` y localizar el run fallido.
2. Revisar el log del step `run_end_to_end_dbt_build` para ver el error de dbt.
3. Consultar las tablas de fallos persistidos por `store_failures`:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select table_name from information_schema.tables
      where table_schema = 'dbt_test_failures' order by table_name;"
```

4. Para cada tabla listada, inspeccionar las filas que fallaron el test:

```bash
docker compose -f docker-compose.data.yml exec warehouse psql \
  -U warehouse -d warehouse \
  -c "select * from dbt_test_failures.<table_name> limit 50;"
```

5. Si el fallo es en los datos fuente, escalar al equipo de la fuente (ver "Datos fuente desactualizados" abajo).
6. Si el fallo es en logica de transformacion, corregir el modelo dbt, hacer deploy y re-ejecutar la particion.
7. No promover resultados a BI hasta que `gold.quality_marks` refleje un estado `passed`.

### Dagster job falla

1. En Dagster UI, entrar al run fallido y revisar el step que fallo.
2. Si el error es transitorio (timeout, connection reset), el `RetryPolicy` ya reintenta hasta 3 veces con backoff exponencial comenzando en 30 s. Si aun asi falla, re-ejecutar manualmente desde la UI con el mismo partition key.
3. Si el error es en el step de extraccion (`load_bronze_produccion_raw` o `load_bronze_pozos_raw`), verificar conectividad con datos.gob.ar y que las variables `PRODUCCION_URL` / `POZOS_URL` esten configuradas.
4. Si el error persiste despues de dos intentos manuales, escalar al tech lead con el run ID y el stack trace.

### Datos fuente desactualizados (freshness gate)

1. El freshness gate de dbt emite un error si la fuente no actualizo dentro de la ventana esperada.
2. Identificar que fuente esta desactualizada (produccion o pozos) revisando el log del step `run_end_to_end_dbt_build`.
3. Contactar al equipo responsable de datos.gob.ar (canal `#upstream-data`) con el periodo afectado.
4. No reprocesar la particion hasta confirmar que la fuente tiene datos actualizados.
5. Una vez confirmado, re-ejecutar la particion con el comando de la seccion "Ejecutar el reproceso".

## Consideraciones operativas

- **Tiempo de ejecucion esperado:** el job completo (bronze + dbt build) toma entre 5 y 15 minutos segun el volumen mensual.
- **SLA de frescura:** el pipeline mensual debe completarse antes de las 06:00 ART del dia 1 de cada mes. El schedule dispara a las 03:00 ART, dejando un margen de 3 horas.
- **Almacenamiento:** bronze retiene todas las particiones históricas. Un backfill completo desde 2026-01 puede ocupar varios GB; coordinar con el DBA antes de reprocesar mas de 6 meses consecutivos.
- **Concurrencia:** no ejecutar dos runs del mismo job en paralelo sobre la misma particion; los `DELETE` en bronze no son atomicos entre runs distintos.

## Decisiones documentadas

**Funcional — dbt build en lugar de dbt run + dbt test por separado:**
`end_to_end_data_job` invoca `dbt build` como comando unico. Esto garantiza que los tests se ejecutan sobre los mismos modelos que acaban de materializarse y que, si algun test falla, dbt no promueve los modelos downstream. Ejecutar `dbt run` seguido de `dbt test` por separado permitiria que un fallo en los tests ocurra despues de que los datos ya estuvieran disponibles para BI, rompiendo la garantia de calidad.

**No funcional — RetryPolicy con backoff exponencial en lugar de delay fijo:**
Todos los ops usan `RetryPolicy(max_retries=3, delay=30, backoff=Backoff.EXPONENTIAL)`. Los fallos transitorios tipicos en este pipeline son bloqueos de warehouse o timeouts HTTP a datos.gob.ar. Ambos tipos de error tienden a resolverse con mayor tiempo entre reintentos: un lock liberado tarda mas en re-adquirirse si el reintento llega mas tarde, y un endpoint con rate-limit recupera cuota mas rapido si se espera mas. Un delay fijo de 30 s podria coincidir con el patron del lock y fallar sistematicamente; el backoff exponencial reduce esa probabilidad.
