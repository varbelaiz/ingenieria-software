{{ config(materialized='view', schema='gold') }}

with checks as (

    select
        'dim_pozo_completeness' as check_name,
        'dim_pozo' as dimension,
        count(*) filter (
            where pozo_key is null
               or id_pozo is null
               or sigla is null
               or formacion_productiva is null
               or id_empresa is null
               or area is null
               or cuenca is null
               or tipo_recurso is null
               or is_current is null
        )::bigint as failed_rows
    from {{ ref('dim_pozo') }}

    union all

    select
        'dim_empresa_completeness' as check_name,
        'dim_empresa' as dimension,
        count(*) filter (
            where empresa_key is null
               or id_empresa is null
               or empresa is null
               or is_current is null
        )::bigint as failed_rows
    from {{ ref('dim_empresa') }}

    union all

    select
        'dim_fecha_valid_month' as check_name,
        'dim_fecha' as dimension,
        count(*) filter (
            where fecha_key is null
               or periodo is null
               or mes is null
               or mes < 1
               or mes > 12
        )::bigint as failed_rows
    from {{ ref('dim_fecha') }}

    union all

    select
        'fct_produccion_measure_ranges' as check_name,
        'fct_produccion' as dimension,
        count(*) filter (
            where prod_gas < 0
               or prod_petroleo < 0
               or prod_agua < 0
               or dias_produccion < 0
               or dias_produccion > 31
        )::bigint as failed_rows
    from {{ ref('fct_produccion') }}

    union all

    select
        'fct_produccion_fact_grain' as check_name,
        'fct_produccion' as dimension,
        coalesce(sum(duplicate_rows), 0)::bigint as failed_rows
    from (
        select count(*) - 1 as duplicate_rows
        from {{ ref('fct_produccion') }}
        group by id_pozo, periodo
        having count(*) > 1
    ) as duplicates

    union all

    select
        'fct_produccion_rel_pozo' as check_name,
        'fct_produccion' as dimension,
        count(*) filter (where pozo.pozo_key is null)::bigint as failed_rows
    from {{ ref('fct_produccion') }} as fact
    left join {{ ref('dim_pozo') }} as pozo
        on fact.pozo_key = pozo.pozo_key

    union all

    select
        'fct_produccion_rel_empresa' as check_name,
        'fct_produccion' as dimension,
        count(*) filter (where empresa.empresa_key is null)::bigint as failed_rows
    from {{ ref('fct_produccion') }} as fact
    left join {{ ref('dim_empresa') }} as empresa
        on fact.empresa_key = empresa.empresa_key

    union all

    select
        'fct_produccion_rel_fecha' as check_name,
        'fct_produccion' as dimension,
        count(*) filter (where fecha.fecha_key is null)::bigint as failed_rows
    from {{ ref('fct_produccion') }} as fact
    left join {{ ref('dim_fecha') }} as fecha
        on fact.fecha_key = fecha.fecha_key

)

select
    check_name,
    dimension,
    case
        when failed_rows = 0 then 'PASS'
        else 'ERROR'
    end as status,
    failed_rows,
    current_timestamp as checked_at
from checks
