{{ config(materialized='table', tags=['pre_ia']) }}

{#-
  TODAS as notícias ainda não classificadas da janela, com a pontuação do pré-filtro e o MOTIVO de
  admissão/exclusão. É a tabela de AUDITORIA do filtro: para saber por que uma notícia não chegou à IA,
  consulte-a (ex.: select * from prata.prata_noticias_pontuadas where not admitida order by pontuacao desc).
  A fila que a IA consome é prata_noticias_candidatas (só as admitidas). Regras e listas de termos em
  macros/termos_pre_filtro.sql.
-#}
{% set T = termos_pre_filtro() %}

with base as (
    select
        n.titulo, n.data_publicacao, n.fonte, n.resumo_html, n.url_noticia,
        {{ normalizar_texto(sem_sufixo_fonte('n.titulo')) }}   as t_titulo,
        {{ normalizar_texto(sem_html('n.resumo_html')) }}      as t_resumo,
        {{ normalizar_texto("substring(n.titulo from '\s+[-|–—]\s+([^-|–—]{2,60})$')") }} as t_portal
    from {{ ref('bronze_noticias') }} n
    where n.data_publicacao >= current_date - {{ var('dias_retroativos', 7) | int }}
      and not exists (
            select 1 from {{ ref('bronze_classificacoes_ia') }} c where c.titulo = n.titulo
      )
),

base_limpa as (
    -- o resumo do Google News repete o título COM o portal (<a>Título - Portal</a>): o portal sai do resumo,
    -- senão "Plataforma Media" vira contexto de plataforma de petróleo
    select
        titulo, data_publicacao, fonte, resumo_html, url_noticia, t_titulo,
        case when t_portal is not null and length(t_portal) >= 3
             then replace(t_resumo, t_portal, ' ') else t_resumo end as t_resumo
    from base
),

sinais as (
    select
        titulo, data_publicacao, fonte, resumo_html, url_noticia,
        {{ tem_algum_termo("(t_titulo || ' ' || t_resumo)", T['contexto_forte']) }}  as ctx_forte,
        {{ tem_algum_termo("(t_titulo || ' ' || t_resumo)", T['contexto_fraco']) }}  as ctx_fraco,
        case when fonte = any(array[{% for f in T['fontes_contexto_forte'] %}'{{ f }}'{% if not loop.last %}, {% endif %}{% endfor %}])
             then 1 else 0 end                                                          as ctx_fonte,
        case when fonte like '{{ T["prefixo_google_news"] }}%' then 1 else 0 end        as bonus_google,
        {{ contar_termos("(t_titulo || ' ' || t_resumo)", T['incidente_forte']) }}   as hits_forte,
        {{ contar_termos("(t_titulo || ' ' || t_resumo)", T['incidente_fraco']) }}   as hits_fraco,
        {{ tem_algum_termo("(t_titulo || ' ' || t_resumo)", T['ruido']) }}           as ruido,
        {{ tem_algum_termo("(t_titulo || ' ' || t_resumo)", T['ruido_rodoviario']) }} as ruido_rodoviario,
        {{ tem_algum_termo("(t_titulo || ' ' || t_resumo)", T['ruido_exterior']) }}  as ruido_exterior,
        {{ tem_algum_termo("(t_titulo || ' ' || t_resumo)", T['indicio_brasil']) }}  as indicio_brasil,
        {{ tem_algum_termo("(t_titulo || ' ' || t_resumo)", T['nucleo_pg']) }}       as nucleo_pg
    from base_limpa
),

pontuadas as (
    select
        *,
        4 * ctx_forte + ctx_fraco + 4 * ctx_fonte + bonus_google
        + 3 * least(hits_forte, 2) + least(hits_fraco, 2)
        - 6 * ruido
        - 6 * (ruido_rodoviario * (1 - nucleo_pg))
        - 6 * ruido_exterior
        - 6 * (ruido_exterior * (1 - indicio_brasil))                           as pontuacao
    from sinais
)

select
    titulo, data_publicacao, fonte, resumo_html, url_noticia,
    pontuacao, ctx_forte, ctx_fraco, ctx_fonte, bonus_google, hits_forte, hits_fraco, ruido,
    ruido_rodoviario, ruido_exterior, indicio_brasil, nucleo_pg,
    case
        when (ctx_forte + ctx_fraco + ctx_fonte) = 0                  then 'excluida: sem contexto de P&G'
        when hits_forte = 0 and hits_fraco < 2                        then 'excluida: sem sinal de incidente'
        when pontuacao < {{ T['pontuacao_minima'] }}                  then 'excluida: pontuacao baixa (ruido, exterior ou sinais fracos)'
        else 'admitida'
    end                                                                        as motivo_filtro,
    (    (ctx_forte + ctx_fraco + ctx_fonte) > 0
     and (hits_forte >= 1 or hits_fraco >= 2)
     and pontuacao >= {{ T['pontuacao_minima'] }})                             as admitida
from pontuadas
