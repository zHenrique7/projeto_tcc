{{ config(tags=['pos_ia']) }}

{#-
  OURO: Validador: cruza cada incidente da IA com a base oficial SISO (ANP) em cascata (waterfall),
  sempre na janela [data_fato - janela_siso_dias, data_fato]:
    0 - Match Perfeito              : chave da IA == nome oficial da instalação no SISO
    1 - Match por Substring         : chave (>= 6 caracteres) no início/fim do nome oficial, ou nome oficial no título
    5 - Match por Localidade        : campo da IA no endereço da instalação (somente se a IA não identificou instalação)
  999 - Nao Comunicado              : sem correspondência
  Uma linha por notícia; vence o menor score e, no empate, a data mais próxima do fato.
-#}
{% set janela = var('janela_siso_dias') | int %}

with ia_base as (
    select
        i.*,
        coalesce(i.ia_data_fato, i.data_publicacao::date)   as ia_data_conv,
        {{ limpar_e_desacentuar('i.ia_instalacao') }}        as ia_nome_limpo,
        {{ limpar_e_desacentuar('i.ia_sonda') }}             as ia_sonda_limpo,
        {{ limpar_e_desacentuar('i.ia_poco') }}              as ia_poco_limpo,
        {{ limpar_e_desacentuar('i.ia_campo') }}             as ia_campo_limpo,
        {{ limpar_e_desacentuar('i.titulo') }}               as ia_titulo_limpo
    from {{ ref('incidentes_ia') }} i
),

-- Tradução da instalação pela dimensão oficial: feita uma única vez em prata_instalacao_ia
ia as (
    select
        b.*,
        p.dm_nome_limpo,
        p.ia_chave_busca
    from ia_base b
    join {{ ref('prata_instalacao_ia') }} p
      on p.id_noticia = md5(b.titulo || '|' || b.data_publicacao::text)
),

siso as (
    select * from {{ ref('prata_siso_incidentes') }}
),

-- Camada 1: match exato
match_exato as (
    select
        ia.titulo, s.num_incidente, s.dsc_empresa, s.nom_instalacao, s.dat_primeira_obs,
        0 as score_distancia,
        'Match Perfeito' as status_cruzamento,
        row_number() over (
            partition by ia.titulo order by abs(ia.ia_data_conv - s.siso_data)
        ) as rk
    from ia
    join siso s
      on s.siso_data between ia.ia_data_conv - {{ janela }} and ia.ia_data_conv
     and ia.ia_chave_busca is not null
     and ia.ia_chave_busca not in ('', 'NAOINFORMADO')
     and ia.ia_chave_busca = s.siso_nome_limpo
),

exato as (
    select titulo, num_incidente, dsc_empresa, nom_instalacao, dat_primeira_obs, score_distancia, status_cruzamento
    from match_exato where rk = 1
),

-- Camada 2: substring / sigla (blindada contra falsos positivos)
substring_match as (
    select
        ia.titulo, s.num_incidente, s.dsc_empresa, s.nom_instalacao, s.dat_primeira_obs,
        1 as score_distancia,
        'Match por Substring' as status_cruzamento
    from ia
    join siso s
      on s.siso_data between ia.ia_data_conv - {{ janela }} and ia.ia_data_conv
     and (
            (
                length(ia.ia_chave_busca) >= 6
                and (
                    s.siso_nome_limpo like ia.ia_chave_busca || '%'
                    or s.siso_nome_limpo like '%' || ia.ia_chave_busca
                )
            )
         or (
                length(s.siso_nome_limpo) >= 6
                and s.siso_nome_limpo !~ '^[0-9]'
                and ia.ia_titulo_limpo like '%' || s.siso_nome_limpo || '%'
            )
     )
    where not exists (select 1 from exato e where e.titulo = ia.titulo)
),

-- Camada 3: localidade / campo (somente quando a IA não identificou a instalação)
fallback as (
    select
        ia.titulo, s.num_incidente, s.dsc_empresa, s.nom_instalacao, s.dat_primeira_obs,
        5 as score_distancia,
        'Match por Localidade (Fallback)' as status_cruzamento
    from ia
    join siso s
      on s.siso_data between ia.ia_data_conv - {{ janela }} and ia.ia_data_conv
     and ia.ia_campo_limpo not in ('', 'NAOINFORMADO')
     and s.siso_ende_limpo like '%' || ia.ia_campo_limpo || '%'
    where (ia.ia_chave_busca is null or ia.ia_chave_busca in ('', 'NAOINFORMADO'))
      and not exists (select 1 from exato e where e.titulo = ia.titulo)
      and not exists (select 1 from substring_match m where m.titulo = ia.titulo)
),

-- Camada 4: sem correspondência
sem_match as (
    select
        ia.titulo,
        null::text      as num_incidente,
        null::text      as dsc_empresa,
        null::text      as nom_instalacao,
        null::timestamp as dat_primeira_obs,
        999             as score_distancia,
        'Nao Comunicado / Sem Correspondencia' as status_cruzamento
    from ia
    where not exists (select 1 from exato e where e.titulo = ia.titulo)
      and not exists (select 1 from substring_match m where m.titulo = ia.titulo)
      and not exists (select 1 from fallback f where f.titulo = ia.titulo)
),

todos as (
    select * from exato
    union all select * from substring_match
    union all select * from fallback
    union all select * from sem_match
),

melhor as (
    select
        t.*,
        row_number() over (
            partition by t.titulo
            order by
                t.score_distancia asc,
                abs(t.dat_primeira_obs::date - ia.ia_data_conv) asc nulls last,
                t.num_incidente
        ) as rk_final
    from todos t
    join ia on ia.titulo = t.titulo
)

select
    ia.data_publicacao,
    ia.fonte,
    ia.titulo,
    ia.url_noticia,
    ia.ia_severidade,
    ia.ia_confianca,
    ia.ia_tipo_evento,
    ia.ia_instalacao,
    ia.ia_sonda,
    ia.ia_poco,
    ia.ia_campo,
    ia.ia_municipio,
    ia.ia_estado,
    ia.ia_operadora_contrato,
    ia.ia_operadora_inst,
    ia.ia_vitimas,
    ia.ia_data_fato,
    ia.ia_data_conv,
    ia.dm_nome_limpo                                       as instalacao_dm_limpa,
    ia.ia_motivo,
    ia.qtd_noticias_do_evento,
    m.num_incidente,
    m.dsc_empresa,
    m.nom_instalacao,
    m.dat_primeira_obs,
    m.score_distancia,
    m.status_cruzamento,
    (m.num_incidente is not null) as comunicado_siso,
    ia.data_carga
from ia
join melhor m on m.titulo = ia.titulo and m.rk_final = 1
