{{ config(materialized='table', schema='silver') }}

-- Silver staging del listado de pozos: datos de referencia, materializados como
-- tabla (override del default incremental de la capa silver, que no aplica a una
-- dimensión sin grano temporal). Deduplica al registro más reciente por pozo.

with source as (

    select *
    from {{ source('bronze', 'pozos_raw') }}
    where nullif(trim(idpozo), '') is not null

),

deduped as (

    select
        nullif(trim(idpozo), '')::bigint    as id_pozo,
        nullif(trim(sigla), '')             as sigla,
        nullif(trim(formprod), '')          as formacion_productiva,
        upper(trim(idempresa))              as id_empresa,
        _loaded_at,
        row_number() over (
            partition by nullif(trim(idpozo), '')::bigint
            order by _loaded_at desc
        ) as _row_num
    from source

)

select
    id_pozo,
    sigla,
    formacion_productiva,
    id_empresa,
    _loaded_at
from deduped
where _row_num = 1
