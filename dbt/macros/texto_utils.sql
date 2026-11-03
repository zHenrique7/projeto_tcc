{#- Utilitários de texto usados pelo pré-filtro de notícias (prata_noticias_candidatas). -#}

{#- minúsculas e sem acento (requer a extensão unaccent) -#}
{% macro normalizar_texto(expr) -%}
lower(unaccent(coalesce({{ expr }}, '')))
{%- endmacro %}

{#- remove o sufixo " - Nome do Portal" que o Google News acrescenta ao título -#}
{% macro sem_sufixo_fonte(col) -%}
regexp_replace({{ col }}, '\s+[-|–—]\s+[^-|–—]{2,60}$', '')
{%- endmacro %}

{#- remove tags HTML do resumo do RSS e o nome do portal (<font>Portal</font>) que o Google News coloca no resumo:
    sem isso, "Plataforma Media" ou "Rádio Itatiaia" viram palavras de contexto/ruído. -#}
{% macro sem_html(col) -%}
regexp_replace(
    regexp_replace(coalesce({{ col }}, ''), '<font[^>]*>[^<]*</font>', ' ', 'gi'),
    '<[^>]*>', ' ', 'g')
{%- endmacro %}

{#- 1 se o texto contém ao menos um dos termos (palavra inteira; cada termo é um fragmento de regex sem acento) -#}
{% macro tem_algum_termo(coluna, termos) -%}
(case when {{ coluna }} ~ '\m(?:{{ termos | join("|") }})\M' then 1 else 0 end)
{%- endmacro %}

{#- quantidade de termos DISTINTOS da lista que aparecem no texto -#}
{% macro contar_termos(coluna, termos) -%}
(
{%- for t in termos %}
    (case when {{ coluna }} ~ '\m(?:{{ t }})\M' then 1 else 0 end){% if not loop.last %} +{% endif %}
{%- endfor %}
)
{%- endmacro %}
