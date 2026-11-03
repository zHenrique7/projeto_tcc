{{ config(tags=['pos_ia']) }}

{#-
  PRATA: dimensão unificada de instalações (nome + sigla) e dutos (só nome), com as chaves já limpas.
  Traduz sigla ou nome informal ("P-52", "Plataforma de Mexilhão") para o nome oficial usado no SISO.
  Mantém também o nome/sigla originais e o tipo, que alimentam ouro.dim_instalacao.
-#}
with instalacoes as (
    select nom_identificacao as nome, sig_instalacao as sigla, 'Instalação' as tipo
    from {{ ref('bronze_dm_instalacao') }}
),

dutos as (
    select nom_instalacao as nome, null::text as sigla, 'Duto' as tipo
    from {{ ref('bronze_dm_duto') }}
),

unificada as (
    select * from instalacoes
    union all
    select * from dutos
)

select distinct
    {{ limpar_e_desacentuar('sigla') }} as dm_sigla_limpa,
    {{ limpar_e_desacentuar('nome') }}  as dm_nome_limpo,
    nome                                as dm_nome,
    sigla                               as dm_sigla,
    tipo                                as dm_tipo
from unificada
