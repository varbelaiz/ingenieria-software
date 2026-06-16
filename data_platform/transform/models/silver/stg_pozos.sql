{{ config(materialized='table', schema='silver') }}

-- Silver staging del listado de pozos: datos de referencia, materializados como
-- tabla (override del default incremental de la capa silver, que no aplica a una
-- dimensión sin grano temporal). Deduplica al registro más reciente por pozo.

with source as (

    select *
    from {{ source('bronze', 'pozos_raw') }}
    where nullif(trim(idpozo), '') is not null

),

deduped as (

    select
        nullif(trim(idpozo), '')::bigint    as id_pozo,
        nullif(trim(sigla), '')             as sigla,
        coalesce(nullif(trim(formprod), ''), 'SIN DATO') as formacion_productiva,
        upper(trim(idempresa))              as id_empresa,
        nullif(trim({{ bronze_text_column(source('bronze', 'pozos_raw'), ['empresa', 'operador'], 'idempresa') }}), '') as empresa,
        -- Igual que en produccion: `area`/`tipo_recurso` planas vienen vacías en la
        -- fuente real. Para pozos el tipo de recurso poblado es `tipo_reservorio`
        -- (no existe `tipo_de_recurso`). Unknown member 'SIN DATO' para gaps genuinos.
        coalesce(nullif(trim({{ bronze_text_column(source('bronze', 'pozos_raw'), ['areayacimiento', 'areapermisoconcesion', 'area'], 'NULL') }}), ''), 'SIN DATO') as area,
        coalesce(nullif(trim({{ bronze_text_column(source('bronze', 'pozos_raw'), ['cuenca'], 'NULL') }}), ''), 'SIN DATO') as cuenca,
        coalesce(nullif(trim({{ bronze_text_column(source('bronze', 'pozos_raw'), ['tipo_de_recurso', 'tipo_reservorio', 'sub_tipo_recurso', 'subtipo_reservorio', 'tipo_recurso', 'tiporecurso', 'recurso'], 'NULL') }}), ''), 'SIN DATO') as tipo_recurso,
        _loaded_at,
        row_number() over (
            partition by nullif(trim(idpozo), '')::bigint
            order by _loaded_at desc
        ) as _row_num
    from source

)

select
    id_pozo,
    sigla,
    formacion_productiva,
    id_empresa,
    empresa,
    area,
    cuenca,
    tipo_recurso,
    _loaded_at
from deduped
where _row_num = 1
