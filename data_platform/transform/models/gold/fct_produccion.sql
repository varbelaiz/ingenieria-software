{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['id_pozo', 'periodo'],
    schema='gold'
) }}

with produccion as (

    select *
    from {{ ref('stg_produccion') }}

    {% if is_incremental() %}
      where (
        _loaded_at > (select max(_loaded_at) from {{ this }})
        {% if var('reprocess_period', none) %}
        or periodo = '{{ var("reprocess_period") }}'::date
        {% endif %}
      )
    {% endif %}

),

joined as (

    select
        pozo.pozo_key,
        empresa.empresa_key,
        area.area_key,
        cuenca.cuenca_key,
        tipo.tipo_recurso_key,
        fecha.fecha_key,
        produccion.id_pozo,
        produccion.id_empresa,
        produccion.periodo,
        produccion.prod_gas,
        produccion.prod_petroleo,
        produccion.prod_agua,
        produccion.dias_produccion,
        produccion._loaded_at
    from produccion
    inner join {{ ref('dim_pozo') }} as pozo
        on produccion.id_pozo = pozo.id_pozo
       and pozo.is_current
    inner join {{ ref('dim_empresa') }} as empresa
        on produccion.id_empresa = empresa.id_empresa
       and empresa.is_current
    inner join {{ ref('dim_area') }} as area
        on produccion.area = area.area
    inner join {{ ref('dim_cuenca') }} as cuenca
        on produccion.cuenca = cuenca.cuenca
    inner join {{ ref('dim_tipo_recurso') }} as tipo
        on produccion.tipo_recurso = tipo.tipo_recurso
    inner join {{ ref('dim_fecha') }} as fecha
        on produccion.periodo = fecha.periodo

)

select
    {{ dbt_utils.generate_surrogate_key(['id_pozo', 'periodo']) }} as produccion_key,
    pozo_key,
    empresa_key,
    area_key,
    cuenca_key,
    tipo_recurso_key,
    fecha_key,
    id_pozo,
    id_empresa,
    periodo,
    prod_gas,
    prod_petroleo,
    prod_agua,
    dias_produccion,
    _loaded_at
from joined
