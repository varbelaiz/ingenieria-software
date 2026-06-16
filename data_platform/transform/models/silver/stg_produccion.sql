{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['id_pozo', 'periodo'],
    schema='silver'
) }}

-- Silver staging de producción mensual: tipa volúmenes y fechas, normaliza claves
-- y deduplica al registro más reciente por (pozo, período). La estrategia merge
-- absorbe las correcciones retroactivas que publica datos.gob.ar (ver ADR-13).

with source as (

    select *
    from {{ source('bronze', 'produccion_raw') }}
    where nullif(trim(idpozo), '') is not null
      and nullif(trim(anio), '') is not null
      and nullif(trim(mes), '') is not null

    {% if is_incremental() %}
      and (
        _loaded_at > (select max(_loaded_at) from {{ this }})
        {% if var('reprocess_period', none) %}
        or make_date(anio::int, mes::int, 1) = '{{ var("reprocess_period") }}'::date
        {% endif %}
      )
    {% endif %}

),

typed as (

    select
        nullif(trim(idpozo), '')::bigint        as id_pozo,
        upper(trim(idempresa))                  as id_empresa,
        nullif(trim({{ bronze_text_column(source('bronze', 'produccion_raw'), ['empresa', 'operador'], 'idempresa') }}), '') as empresa,
        -- En la fuente real las columnas planas `area`/`tipo_recurso` existen pero
        -- vienen vacías; los valores poblados viven en `areayacimiento` y
        -- `tipo_de_recurso`. Se priorizan esas y se cae a un unknown member
        -- ('SIN DATO') para los gaps genuinos, evitando NULLs en las dimensiones.
        coalesce(nullif(trim({{ bronze_text_column(source('bronze', 'produccion_raw'), ['areayacimiento', 'areapermisoconcesion', 'area'], 'NULL') }}), ''), 'SIN DATO') as area,
        coalesce(nullif(trim({{ bronze_text_column(source('bronze', 'produccion_raw'), ['cuenca'], 'NULL') }}), ''), 'SIN DATO') as cuenca,
        coalesce(nullif(trim({{ bronze_text_column(source('bronze', 'produccion_raw'), ['tipo_de_recurso', 'sub_tipo_recurso', 'tipo_recurso', 'tiporecurso', 'recurso'], 'NULL') }}), ''), 'SIN DATO') as tipo_recurso,
        make_date(anio::int, mes::int, 1)       as periodo,
        nullif(trim(prod_gas), '')::numeric     as prod_gas,
        nullif(trim(prod_pet), '')::numeric     as prod_petroleo,
        nullif(trim(prod_agua), '')::numeric    as prod_agua,
        coalesce(nullif(trim({{ bronze_text_column(source('bronze', 'produccion_raw'), ['dias_produccion', 'diasprod', 'diasefectivos'], 'NULL') }}), '')::integer, 0) as dias_produccion,
        _loaded_at
    from source

),

deduped as (

    select
        *,
        row_number() over (
            partition by id_pozo, periodo
            order by _loaded_at desc
        ) as _row_num
    from typed

)

select
    id_pozo,
    id_empresa,
    empresa,
    area,
    cuenca,
    tipo_recurso,
    periodo,
    prod_gas,
    prod_petroleo,
    prod_agua,
    dias_produccion,
    _loaded_at
from deduped
where _row_num = 1
  -- Silver excluye filas con volumen negativo: producción negativa es físicamente
  -- inválida para el grano (pozo x mes). La fuente publica algunos negativos como
  -- ajustes retroactivos; se descartan acá para no propagar medidas inválidas a gold.
  and coalesce(prod_gas, 0) >= 0
  and coalesce(prod_petroleo, 0) >= 0
  and coalesce(prod_agua, 0) >= 0
