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

grouped as (

    select
        id_pozo,
        max(sigla) as sigla,
        max(formacion_productiva) as formacion_productiva,
        max(id_empresa) as id_empresa,
        max(area) as area,
        max(cuenca) as cuenca,
        max(tipo_recurso) as tipo_recurso,
        min(_loaded_at) as valid_from
    from pozos
    group by id_pozo

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
from grouped
