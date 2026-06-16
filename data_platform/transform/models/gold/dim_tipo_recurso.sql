{{ config(materialized='table', schema='gold') }}

with tipos as (

    select tipo_recurso from {{ ref('stg_pozos') }}
    union
    select tipo_recurso from {{ ref('stg_produccion') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['tipo_recurso']) }} as tipo_recurso_key,
    tipo_recurso
from tipos
where tipo_recurso is not null
