{{ config(materialized='table', schema='gold') }}

with empresas as (

    select
        id_empresa,
        coalesce(empresa, id_empresa) as empresa,
        _loaded_at
    from {{ ref('stg_pozos') }}

    union all

    select
        id_empresa,
        coalesce(empresa, id_empresa) as empresa,
        _loaded_at
    from {{ ref('stg_produccion') }}

),

grouped as (

    select
        id_empresa,
        max(empresa) as empresa,
        min(_loaded_at) as valid_from
    from empresas
    where id_empresa is not null
    group by id_empresa

)

select
    {{ dbt_utils.generate_surrogate_key(['id_empresa']) }} as empresa_key,
    id_empresa,
    empresa,
    valid_from,
    null::timestamptz as valid_to,
    true as is_current
from grouped
