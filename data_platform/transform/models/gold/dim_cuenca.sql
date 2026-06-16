{{ config(materialized='table', schema='gold') }}

with cuencas as (

    select cuenca from {{ ref('stg_pozos') }}
    union
    select cuenca from {{ ref('stg_produccion') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['cuenca']) }} as cuenca_key,
    cuenca
from cuencas
where cuenca is not null
