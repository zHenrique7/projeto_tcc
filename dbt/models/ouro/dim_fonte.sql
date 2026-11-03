{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA: fontes (feeds) das notícias. tipo_fonte separa o que veio do Google News (busca por termo, mais
  ruído) das fontes especializadas e sindicais (RSS direto). Chave 0 = fonte desconhecida.
-#}
with fontes as (
    select
        {{ chave_natural('fonte') }}  as chave_natural,
        min(trim(fonte))              as fonte,
        case when min(trim(fonte)) like 'GNews%' then 'Google News' else 'Portal especializado / sindical' end as tipo_fonte
    from {{ ref('prata_classificacoes_ia') }}
    where {{ chave_natural('fonte') }} is not null
    group by 1
)

select row_number() over (order by chave_natural)::int as chave_fonte, chave_natural, fonte, tipo_fonte
from fontes

union all

select 0, null, 'Não Informada', 'Não Informada'
