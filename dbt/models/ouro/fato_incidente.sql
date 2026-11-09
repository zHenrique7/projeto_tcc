{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA - FATO: uma linha por INCIDENTE (evento físico) aprovado pela IA, já cruzado com o SISO.
  Mesma granularidade e mesma base dos alertas (ouro.incidentes_cruzados).
  chave_data_fato usa a data do fato extraída pela IA; sem ela, a data de publicação.
  A instalação vem da tradução pela dimensão oficial; se a notícia não permitiu, usa a instalação do incidente SISO
  encontrado no cruzamento. id_incidente é um número incremental (1, 2, 3...) na ordem em que os incidentes foram
  classificados; chave_evento guarda o hash da primeira notícia do evento (o mesmo valor de chave_evento em
  fato_noticia_ia) só para rastreio. Tipo de evento, severidade e status do cruzamento ficam como texto na fato
  (severidade_ordem e status_ordem servem para ordenar no Power BI).
-#}
with base as (
    select
        c.*,
        coalesce(
            c.instalacao_dm_limpa,
            nullif({{ limpar_e_desacentuar('c.nom_instalacao') }}, '')
        )                                                                       as nome_limpo_instalacao
    from {{ ref('incidentes_cruzados') }} c
)

select
    row_number() over (order by b.data_carga, b.titulo)::int                    as id_incidente,
    b.chave_evento,
    {{ chave_data('b.ia_data_conv') }}                                          as chave_data_fato,
    {{ chave_data('b.data_publicacao') }}                                       as chave_data_publicacao,
    coalesce(f.chave_fonte, 0)                                                  as chave_fonte,
    coalesce(l.chave_localidade, 0)                                             as chave_localidade,
    coalesce(i.chave_instalacao, 0)                                             as chave_instalacao,
    b.ia_tipo_evento                                                            as tipo_evento,
    b.ia_severidade                                                             as severidade,
    {{ severidade_ordem('b.ia_severidade') }}                                   as severidade_ordem,
    b.status_cruzamento,
    case b.status_cruzamento
        when 'Match Perfeito' then 1 when 'Match por Substring' then 2
        when 'Match por Localidade (Fallback)' then 3 else 4
    end                                                                         as status_ordem,
    b.comunicado_siso,
    b.num_incidente                                                             as num_incidente_siso,
    b.ia_confianca                                                              as confianca,
    b.ia_vitimas                                                                as vitimas,
    b.qtd_noticias_do_evento,
    b.titulo,
    b.url_noticia,
    b.ia_motivo                                                                 as motivo,
    b.data_carga
from base b
left join {{ ref('dim_instalacao') }} i  on i.chave_natural = b.nome_limpo_instalacao
left join {{ ref('dim_fonte') }} f       on f.chave_natural = {{ chave_natural('b.fonte') }}
left join {{ ref('dim_localidade') }} l  on l.chave_natural = {{ chave_natural_localidade('b.ia_municipio', 'b.ia_estado') }}
