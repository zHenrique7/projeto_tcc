{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA: instalações e dutos oficiais (dimensões da ANP), mais instalações que aparecem só no SISO.
  nome_limpo é a chave de ligação com a tradução feita em prata_instalacao_ia e com o SISO.
  Instalações que a notícia não permite identificar caem no membro desconhecido (chave 0).
-#}
with oficiais as (
    select
        dm_nome_limpo                    as nome_limpo,
        min(dm_nome)                     as instalacao,
        min(dm_sigla)                    as sigla,
        min(dm_tipo)                     as tipo,
        'Dimensão ANP'                   as origem
    from {{ ref('prata_dm_instalacoes') }}
    where dm_nome_limpo <> ''
    group by dm_nome_limpo
),

so_siso as (
    select
        s.siso_nome_limpo                as nome_limpo,
        min(s.nom_instalacao)            as instalacao,
        null::text                       as sigla,
        'Instalação'                     as tipo,
        'Somente no SISO'                as origem
    from {{ ref('prata_siso_incidentes') }} s
    where s.siso_nome_limpo <> ''
      and not exists (select 1 from oficiais o where o.nome_limpo = s.siso_nome_limpo)
    group by s.siso_nome_limpo
),

todas as (
    select * from oficiais
    union all
    select * from so_siso
)

select
    row_number() over (order by nome_limpo)::int as chave_instalacao,
    nome_limpo                                   as chave_natural,
    instalacao,
    sigla,
    tipo,
    origem
from todas

union all

select 0, null, 'Não Informada', null, 'Não Informado', 'Desconhecida'
