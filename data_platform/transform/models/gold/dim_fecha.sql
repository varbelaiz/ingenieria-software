{{ config(materialized='table', schema='gold') }}

with fechas as (

    select distinct periodo
    from {{ ref('stg_produccion') }}
    where periodo is not null

)

select
    {{ dbt_utils.generate_surrogate_key(['periodo']) }} as fecha_key,
    periodo,
    extract(year from periodo)::integer as anio,
    extract(month from periodo)::integer as mes,
    extract(quarter from periodo)::integer as trimestre
from fechas
