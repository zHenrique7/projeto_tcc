{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA: instalações e dutos oficiais (dimensões da ANP), mais as que aparecem só no SISO e as que só a
  notícia cita (origem 'Somente na notícia': ativos que a dimensão da ANP não tem, como um PSV ou o "FSO Cidade de
  Macaé"). Sem essa terceira origem, todo incidente cujo ativo não casa com a ANP ficava com chave 0.
  nome_limpo é a chave de ligação com a tradução feita em prata_instalacao_ia e com o SISO.
  Só cai no membro desconhecido (chave 0) o evento cujas notícias não nomeiam nenhum ativo.
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

so_noticia as (
    select
        p.ia_chave_busca                 as nome_limpo,
        min(p.ativo_texto)               as instalacao,
        null::text                       as sigla,
        'Instalação'                     as tipo,
        'Somente na notícia'             as origem
    from {{ ref('prata_instalacao_ia') }} p
    where p.dm_nome_limpo is null
      and p.ia_chave_busca is not null
      and p.ia_chave_busca not in ('', 'NAOINFORMADO')
      and not exists (select 1 from oficiais o where o.nome_limpo = p.ia_chave_busca)
      and not exists (select 1 from so_siso s where s.nome_limpo = p.ia_chave_busca)
      and not exists (select 1 from {{ ref('prata_siso_incidentes') }} z where z.siso_nome_limpo = p.ia_chave_busca)
    group by p.ia_chave_busca
),

todas as (
    select * from oficiais
    union all
    select * from so_siso
    union all
    select * from so_noticia
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
