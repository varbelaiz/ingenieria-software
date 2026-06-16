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

ranked as (

    select
        *,
        row_number() over (
            partition by id_empresa
            order by _loaded_at desc
        ) as _row_num
    from empresas
    where id_empresa is not null

),

latest as (

    select
        id_empresa,
        empresa,
        _loaded_at as valid_from
    from ranked
    where _row_num = 1

)

select
    {{ dbt_utils.generate_surrogate_key(['id_empresa']) }} as empresa_key,
    id_empresa,
    empresa,
    valid_from,
    null::timestamptz as valid_to,
    true as is_current
from latest
