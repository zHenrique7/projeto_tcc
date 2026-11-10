{#-
  Normalização de ativos e de geografia usada para (1) agrupar notícias do MESMO evento físico e (2) montar a
  dimensão de localidade. Tudo opera sobre o que a IA extraiu; nada aqui exige reprocessar a IA.
-#}

{#- Bacia sedimentar normalizada a partir de um texto livre (campo, título, motivo). Nulo se nenhuma bacia reconhecida.
    "Foz do Amazonas", "Margem Equatorial" e "Amapá" são a mesma região para fins de localidade. -#}
{% macro bacia_normalizada(expr) -%}
case
    when {{ expr }} is null then null
    when lower(unaccent({{ expr }})) ~ '(foz do amazonas|margem equatorial|bacia da foz|\mfza\M)'            then 'Foz do Amazonas'
    when lower(unaccent({{ expr }})) ~ '\mbacia de campos\M'                                                  then 'Bacia de Campos'
    when lower(unaccent({{ expr }})) ~ '\mbacia de santos\M'                                                  then 'Bacia de Santos'
    when lower(unaccent({{ expr }})) ~ '\mbacia do espirito santo\M|\mbacia capixaba\M'                       then 'Bacia do Espírito Santo'
    when lower(unaccent({{ expr }})) ~ '\mbacia potiguar\M'                                                   then 'Bacia Potiguar'
    when lower(unaccent({{ expr }})) ~ 'sergipe[- ]alagoas'                                                   then 'Bacia de Sergipe-Alagoas'
    else null
end
{%- endmacro %}

{#- A Foz do Amazonas fica no litoral do Amapá (e Pará), nunca no Amazonas: a IA às vezes devolve "AM". -#}
{% macro estado_corrigido(estado, bacia) -%}
case when {{ bacia }} = 'Foz do Amazonas' and {{ estado }} = 'AM' then 'AP' else {{ estado }} end
{%- endmacro %}

{#- Chave de comparação do ativo entre notícias: maiúsculas, sem acento, sem o tipo genérico ("Sonda", "FPSO",
    "Plataforma"...), grafias Y/K/W unificadas (Skandy = Skandi) e só [A-Z0-9]. Quem usa deve descartar chaves
    curtas (< 3 caracteres) ou "NAOINFORMADO" (ver prata_classificacoes_ia). -#}
{% macro chave_ativo(col) -%}
regexp_replace(
    regexp_replace(
        regexp_replace(translate(unaccent(upper(coalesce(cast({{ col }} as text), ''))), 'YKW', 'ICV'),
                       '\([^)]*\)', '', 'g'),
        '\m(NAVIO[- ]SONDA|SONDA|FPSO|FSO|FPU|PLATAFORMA|UNIDADE|REFINARIA|NAVIO|EMBARCACAO|REBOCADOR|PSV|AHTS|POCO|USINA|TERMINAL|DUTO|GASODUTO|OLEODUTO)\M',
        '', 'g'),
    '[^A-Z0-9]', '', 'g')
{%- endmacro %}

{#- Prioridade do tipo de evento quando várias notícias do mesmo evento divergem (1 = mais específico/grave).
    Parada de produção e evacuação são CONSEQUÊNCIA; o tipo do evento é o fato que as causou. -#}
{% macro tipo_evento_prioridade(expr) -%}
case {{ expr }}
    when 'Fatalidade' then 1 when 'Explosão' then 2 when 'Incêndio' then 3 when 'Vazamento' then 4
    when 'Acidente' then 5 when 'Evacuação' then 6 when 'Shutdown' then 7 else 8
end
{%- endmacro %}
