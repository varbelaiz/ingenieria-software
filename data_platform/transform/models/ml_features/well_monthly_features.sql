{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['well_id', 'as_of_date'],
    schema='ml_features'
) }}

with feature_dates as (

    select distinct
        id_pozo as well_id,
        periodo as as_of_date
    from {{ ref('fct_produccion') }}

    {% if is_incremental() %}
      where (
        _loaded_at > (select max(_loaded_at) from {{ this }})
        {% if var('reprocess_period', none) %}
        or periodo = '{{ var("reprocess_period") }}'::date
        {% endif %}
      )
    {% endif %}

),

history as (

    select
        id_pozo as well_id,
        periodo,
        prod_gas,
        prod_petroleo,
        prod_agua,
        dias_produccion
    from {{ ref('fct_produccion') }}

),

windowed as (

    select
        feature_dates.well_id,
        feature_dates.as_of_date,
        max(history.prod_gas) filter (
            where history.periodo = feature_dates.as_of_date
        ) as gas_production_current,
        avg(history.prod_gas) filter (
            where history.periodo >= feature_dates.as_of_date - interval '2 months'
        ) as gas_production_avg_3m,
        avg(history.prod_gas) filter (
            where history.periodo >= feature_dates.as_of_date - interval '5 months'
        ) as gas_production_avg_6m,
        max(history.prod_petroleo) filter (
            where history.periodo = feature_dates.as_of_date
        ) as oil_production_current,
        max(history.prod_agua) filter (
            where history.periodo = feature_dates.as_of_date
        ) as water_production_current,
        max(history.dias_produccion) filter (
            where history.periodo = feature_dates.as_of_date
        ) as producing_days_available,
        count(distinct history.periodo) as production_months_available
    from feature_dates
    inner join history
        on history.well_id = feature_dates.well_id
       and history.periodo <= feature_dates.as_of_date
    group by
        feature_dates.well_id,
        feature_dates.as_of_date

),

well_attributes as (

    select
        id_pozo as well_id,
        formacion_productiva as formation,
        cuenca as basin,
        tipo_recurso as resource_type
    from {{ ref('dim_pozo') }}
    where is_current

)

select
    windowed.well_id,
    windowed.as_of_date,
    windowed.gas_production_current,
    windowed.gas_production_avg_3m,
    windowed.gas_production_avg_6m,
    windowed.gas_production_current - windowed.gas_production_avg_3m
        as gas_production_trend_3m,
    windowed.oil_production_current,
    windowed.water_production_current,
    windowed.producing_days_available,
    windowed.production_months_available,
    well_attributes.formation,
    well_attributes.basin,
    well_attributes.resource_type
from windowed
inner join well_attributes
    on windowed.well_id = well_attributes.well_id
