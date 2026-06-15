{#
    Materializa cada modelo en el schema medallion literal (silver, gold) en
    lugar del default de dbt que concatena <target_schema>_<custom_schema>.
    Sin custom schema, usa el schema del target (bronze).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
