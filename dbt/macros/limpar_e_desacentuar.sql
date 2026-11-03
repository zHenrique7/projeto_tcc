{#-
  Equivalente PostgreSQL da função limpar_e_desacentuar do notebook:
  maiúsculas, sem acentos, remove trechos entre parênteses, "P-52" -> "PETROBRAS52" e apenas [A-Z0-9].
  Nulos viram string vazia. Requer a extensão unaccent (criada em docker/initdb).
-#}
{% macro limpar_e_desacentuar(coluna) -%}
coalesce(
    upper(trim(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    unaccent(upper(cast({{ coluna }} as text))),
                    '\([^)]*\)', '', 'g'),
                '\mP-?([0-9]+)', 'PETROBRAS\1', 'g'),
            '[^A-Za-z0-9]', '', 'g')
    )),
    ''
)
{%- endmacro %}
