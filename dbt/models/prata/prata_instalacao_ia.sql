{{ config(materialized='table', tags=['pos_ia']) }}

{#-
  PRATA: tradução, em um só lugar, da instalação citada na notícia (sigla ou nome informal, como "P-74") para o
  nome oficial da dimensão de instalações/dutos da ANP. É usada pelo cruzamento com o SISO (ouro.incidentes_cruzados)
  e pelas dimensões/fatos da estrela, para que as duas leituras nunca divirjam.

  dm_nome_limpo  : nome oficial limpo quando sonda/instalação da notícia casa com a dimensão (senão nulo)
  ia_chave_busca : chave usada na busca no SISO = nome oficial, ou (sem tradução) instalação, sonda ou poço da notícia
-#}
with base as (
    select
        id_noticia,
        {{ limpar_e_desacentuar('instalacao') }} as nome_limpo,
        {{ limpar_e_desacentuar('sonda') }}      as sonda_limpa,
        {{ limpar_e_desacentuar('poco') }}       as poco_limpo
    from {{ ref('prata_classificacoes_ia') }}
    where relevante
),

traduzida as (
    select
        b.*,
        d.dm_nome_limpo,
        row_number() over (
            partition by b.id_noticia
            order by (d.dm_nome_limpo is null), d.dm_nome_limpo, d.dm_sigla_limpa
        ) as rn
    from base b
    left join {{ ref('prata_dm_instalacoes') }} d
        on (b.sonda_limpa not in ('', 'NAOINFORMADO') and b.sonda_limpa = d.dm_sigla_limpa)
        or (b.nome_limpo  not in ('', 'NAOINFORMADO') and b.nome_limpo  = d.dm_sigla_limpa)
        or (b.nome_limpo  not in ('', 'NAOINFORMADO') and b.nome_limpo  = d.dm_nome_limpo)
)

select
    id_noticia,
    dm_nome_limpo,
    coalesce(
        case when dm_nome_limpo is not null and dm_nome_limpo <> '' then dm_nome_limpo end,
        case when nome_limpo  not in ('', 'NAOINFORMADO') then nome_limpo  end,
        case when sonda_limpa not in ('', 'NAOINFORMADO') then sonda_limpa end,
        case when poco_limpo  not in ('', 'NAOINFORMADO') then poco_limpo  end
    ) as ia_chave_busca
from traduzida
where rn = 1
