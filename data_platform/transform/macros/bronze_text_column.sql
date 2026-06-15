{% macro bronze_text_column(relation, candidates, default_expression) %}
    {%- if execute -%}
        {%- set relation_columns = adapter.get_columns_in_relation(relation) -%}
        {%- set names = relation_columns | map(attribute='name') | map('lower') | list -%}
        {%- for candidate in candidates -%}
            {%- if candidate | lower in names -%}
                {{ return(adapter.quote(candidate)) }}
            {%- endif -%}
        {%- endfor -%}
    {%- endif -%}
    {{ return(default_expression) }}
{% endmacro %}
