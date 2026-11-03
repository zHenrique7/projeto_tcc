{{ config(tags=['pos_ia']) }}

{#- OURO / ESTRELA: município + estado como a IA extraiu da notícia. Chave 0 = localidade desconhecida. -#}
with locais as (
    select
        {{ chave_natural_localidade('municipio', 'estado') }}   as chave_natural,
        min(trim(municipio))                                    as municipio,
        min(upper(trim(estado)))                                as estado
    from {{ ref('prata_classificacoes_ia') }}
    where {{ chave_natural_localidade('municipio', 'estado') }} is not null
    group by 1
)

select row_number() over (order by chave_natural)::int as chave_localidade, chave_natural,
       coalesce(municipio, 'Não Informado') as municipio, coalesce(estado, 'Não Informado') as estado
from locais

union all

select 0, null, 'Não Informado', 'Não Informado'
