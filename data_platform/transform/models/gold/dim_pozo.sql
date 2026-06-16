{{ config(materialized='table', schema='gold') }}

with pozos as (

    select
        id_pozo,
        sigla,
        formacion_productiva,
        id_empresa,
        area,
        cuenca,
        tipo_recurso,
        _loaded_at
    from {{ ref('stg_pozos') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by id_pozo
            order by _loaded_at desc
        ) as _row_num
    from pozos

),

latest as (

    select
        id_pozo,
        sigla,
        formacion_productiva,
        id_empresa,
        area,
        cuenca,
        tipo_recurso,
        _loaded_at as valid_from
    from ranked
    where _row_num = 1

)

select
    {{ dbt_utils.generate_surrogate_key(['id_pozo']) }} as pozo_key,
    id_pozo,
    sigla,
    formacion_productiva,
    id_empresa,
    area,
    cuenca,
    tipo_recurso,
    valid_from,
    null::timestamptz as valid_to,
    true as is_current
from latest
