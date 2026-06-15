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
        make_date(anio::int, mes::int, 1)       as periodo,
        nullif(trim(prod_gas), '')::numeric     as prod_gas,
        nullif(trim(prod_pet), '')::numeric     as prod_petroleo,
        nullif(trim(prod_agua), '')::numeric    as prod_agua,
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
    periodo,
    prod_gas,
    prod_petroleo,
    prod_agua,
    _loaded_at
from deduped
where _row_num = 1
