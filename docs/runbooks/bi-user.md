# Runbook de BI user

**Rol:** Usuario de BI / Data Owner
**Responsabilidades:** Exploracion de datos gold en Metabase, validacion de frescura y calidad antes de publicar, escalamiento de datos viejos o con fallas al equipo de data engineering.
**Dueño:** Equipo de Negocio / Data Owner.

## Validar frescura y calidad antes de publicar

Este procedimiento confirma que los datos de la capa gold estan frescos y pasaron los
checks de calidad antes de presentar o publicar un reporte de produccion. El disparador es
un pedido de reporte o una reunion donde se van a mostrar metricas de produccion (gas,
petroleo, agua) por cuenca, operadora o pozo. El objetivo es no publicar datos viejos o
que fallaron calidad: la fuente datos.gob.ar corrige meses pasados de forma retroactiva,
asi que un dashboard puede estar mostrando un periodo que el pipeline todavia no
reproceso.

## Prerrequisitos

- Stack de datos levantado (lo administra el data engineer):

```bash
docker compose -f docker-compose.data.yml up --build
```

- Acceso a Metabase en `http://localhost:3002` (BI sobre el esquema `gold`).
- Acceso a DataHub en `http://localhost:9002` (catalogo, freshness y lineage). Para
  levantarlo y publicar metadata, ver [Gobierno de datos](../governance.md).
- Periodo del reporte a presentar (por ejemplo, produccion de `2026-05`).

## Pasos

1. **Abrir el dashboard en Metabase.** Entrar a `http://localhost:3002` y abrir el
   dashboard "Produccion de pozos no convencionales" (provisto por
   `data_platform/bi/provision.py`). Acotar el filtro de rango de fechas "Periodo" al
   periodo que se va a presentar; los KPIs y la card por tipo de recurso (gas, petroleo,
   agua) se recalculan sobre ese rango.

2. **Revisar la marca de calidad.** La vista `gold.quality_marks` resume el ultimo estado
   de cada check. Confirmar que ningun check quedo en `ERROR`:

   ```bash
   docker compose -f docker-compose.data.yml exec warehouse psql \
     -U warehouse -d warehouse \
     -c "select check_name, dimension, status, failed_rows, checked_at
         from gold.quality_marks
         order by checked_at desc;"
   ```

   Todos los `status` deben ser `PASS` (`failed_rows = 0`). Si algun check esta en `ERROR`,
   ir a "Manejo de fallos".

3. **Verificar la ultima actualizacion (freshness) en DataHub.** Abrir
   `http://localhost:9002`, iniciar sesion con `datahub` / `datahub` y buscar el dataset
   `gold.fct_produccion`. Revisar la ultima actualizacion y el lineage
   `bronze.produccion_raw` -> `silver.stg_produccion` -> `gold.fct_produccion`. Confirmar
   que el periodo del reporte esta cargado y dentro de la ventana de frescura. La
   verificacion de freshness desde la fuente se documenta en
   [Gobierno de datos](../governance.md#ver-lineage-y-freshness).

4. **Publicar o presentar.** Solo con la marca de calidad en `PASS` y la frescura dentro
   del umbral, presentar el reporte. En caso contrario, no publicar y escalar.

## Validacion

- `gold.quality_marks` no tiene filas con `status = 'ERROR'` para el periodo a presentar.
- DataHub muestra el periodo del reporte como cargado, con `checked_at` reciente y
  freshness dentro del umbral acordado (ver "Consideraciones no funcionales").

## Manejo de fallos

### Marca de calidad en ERROR

1. No publicar el reporte: un check en `ERROR` significa que la capa gold no cumple el
   contrato de calidad para ese periodo.
2. Identificar el check fallido por `check_name` y `dimension` en `gold.quality_marks`.
3. Escalar al data engineer para que reprocese la particion afectada (ver
   [Runbook de data engineer](data-engineer.md#reprocesar-una-particion-historica)).
4. Re-validar despues del reproceso: el check debe volver a `PASS` antes de publicar.

### Datos desactualizados (freshness fuera de umbral)

1. Si DataHub muestra el periodo como faltante o la ultima actualizacion fuera del umbral,
   no publicar.
2. Confirmar con el data engineer si la fuente datos.gob.ar publico el periodo. Si la
   fuente esta desactualizada, esperar la correccion; no forzar la publicacion con datos
   viejos.
3. Una vez reprocesado el periodo y con la marca en `PASS`, repetir los pasos de
   validacion.

## Consideraciones no funcionales

- **Frescura aceptable:** para reportes mensuales, el periodo presentado debe estar
  cargado antes de las 06:00 ART del dia 1 de cada mes (el schedule del pipeline corre a
  las 03:00 ART; ver el [runbook de data engineer](data-engineer.md#consideraciones-operativas)).
  Presentar un periodo cuya particion todavia no corrio se considera fuera de SLA.
- **Calidad minima:** no se publica con ningun check en `ERROR`. La marca de calidad es la
  unica fuente de verdad para decidir publicacion; no se reemplaza por una inspeccion
  visual del dashboard.
- **Privacidad:** el dataset de datos.gob.ar es publico y agregado por pozo/operadora; no
  contiene PII. Aun asi, los reportes se comparten solo por los canales acordados.

## Decisiones documentadas

**Funcional — la marca de calidad (`gold.quality_marks`) decide la publicacion, no el
dashboard:**
El usuario de BI valida contra `gold.quality_marks` y no contra lo que "se ve bien" en
Metabase. Un dashboard puede renderizar sin errores aunque un check de rango o de grano
haya fallado (por ejemplo, dias_produccion fuera de `0..31` o un grano duplicado). La vista
de marca de calidad expone el resultado real de los checks que corre `dbt build`, asi que
es el criterio operativo correcto: desde el incentivo del data owner, publicar un numero
incorrecto es peor que demorar el reporte.

**No funcional — umbral de frescura atado al SLA del pipeline, no a la fecha del calendario:**
La frescura aceptable se define respecto del schedule mensual del pipeline (03:00 ART del
dia 1, con margen hasta las 06:00) y no respecto de "el mes ya cerro". Esto evita publicar
un periodo cuya particion todavia no se materializo: desde el incentivo del usuario de
negocio de confiar en el dato, es mejor esperar la corrida del pipeline que presentar un
periodo vacio o a medio cargar.
