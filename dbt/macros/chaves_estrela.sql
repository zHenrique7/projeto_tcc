{#-
  Macros do modelo estrela (camada ouro).

  Chaves: cada dimensão (exceto dim_data, que usa a própria data) tem uma chave numérica incremental (1, 2, 3...), gerada
  na reconstrução da tabela. Como dimensões e fatos são reconstruídos juntos a cada execução do dbt, as chaves sempre
  batem entre si. A chave 0 é o membro "desconhecido": quando a notícia não permite identificar a fonte, o local ou a
  instalação, a linha de fato aponta para 0 em vez de ficar com chave nula.

  Para ligar o fato à dimensão sem depender de número, cada dimensão guarda também a chave natural (chave_natural):
  o valor normalizado (minúsculas, sem acento). Esta coluna é só de apoio e pode ficar oculta no Power BI.
-#}

{#- Valor normalizado; nulo quando vazio ou "Não Informado". -#}
{% macro chave_natural(expr) -%}
nullif(nullif(lower(unaccent(trim(cast({{ expr }} as text)))), ''), 'nao informado')
{%- endmacro %}

{% macro chave_natural_localidade(municipio, estado) -%}
case
    when {{ chave_natural(municipio) }} is null and {{ chave_natural(estado) }} is null then null
    else coalesce({{ chave_natural(municipio) }}, '') || '|' || coalesce({{ chave_natural(estado) }}, '')
end
{%- endmacro %}

{#- Ordem de gravidade, para ordenar a severidade no Power BI (1 = mais grave; 5 = não informada). -#}
{% macro severidade_ordem(expr) -%}
case upper(trim({{ expr }}))
    when 'CRÍTICO' then 1 when 'ALTO' then 2 when 'MÉDIO' then 3 when 'INFORMATIVO' then 4 else 5
end
{%- endmacro %}

{#- Datas fora do intervalo de dim_data (ou nulas) caem no membro desconhecido 1900-01-01. -#}
{% macro chave_data(expr) -%}
case
    when cast({{ expr }} as date) between date '2015-01-01' and current_date + 365 then cast({{ expr }} as date)
    else date '1900-01-01'
end
{%- endmacro %}
