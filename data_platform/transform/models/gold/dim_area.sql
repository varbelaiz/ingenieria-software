{{ config(materialized='table', schema='gold') }}

with areas as (

    select area from {{ ref('stg_pozos') }}
    union
    select area from {{ ref('stg_produccion') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['area']) }} as area_key,
    area
from areas
where area is not null
