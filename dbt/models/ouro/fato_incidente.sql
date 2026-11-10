{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA - FATO: uma linha por INCIDENTE (evento físico) aprovado pela IA, já cruzado com o SISO.
  É a base dos alertas por e-mail (alerts.py) e do Power BI. É a tabela COMPLETA do incidente:
  além das chaves das dimensões traz o texto do ativo, do local, das operadoras e os dados do incidente SISO
  encontrado (empresa, instalação, data), então o relatório pode usar só esta fato (mais dim_data) ou, se quiser filtros
  compartilhados com as outras fatos, as dimensões.
  chave_data_fato usa a data do fato do EVENTO (a mais antiga informada pelas notícias); sem ela, a publicação mais
  antiga do evento. Tipo, severidade, ativo e local também são os consolidados do evento (ver prata_classificacoes_ia).
  A instalação vem da tradução pela dimensão oficial; se não houver, a do incidente SISO encontrado no cruzamento; se
  também não houver, o ativo como a IA escreveu (dim_instalacao, origem 'Somente na notícia'). Só cai em 0 quando
  nenhuma notícia do evento nomeou o ativo. A localidade é município+estado ou, offshore, a bacia. id_incidente é a chave numérica do evento (1, 2, 3...), na ordem em que foram
  classificados; é a mesma de fato_noticia_ia.id_incidente (o hash interno do evento fica só na prata). Tipo de evento, severidade e status do cruzamento ficam como texto na fato
  (severidade_ordem e status_ordem servem para ordenar no Power BI).
-#}
with base as (
    select
        c.*,
        coalesce(
            c.instalacao_dm_limpa,
            case when c.status_cruzamento in ('Match Perfeito', 'Match por Substring')
                 then nullif({{ limpar_e_desacentuar('c.nom_instalacao') }}, '') end,
            nullif(nullif(c.instalacao_chave_busca, ''), 'NAOINFORMADO')
        )                                                                       as nome_limpo_instalacao
    from {{ ref('prata_incidentes_cruzados') }} c
)

select
    b.id_incidente,
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
    b.data_publicacao,
    b.ia_data_conv                                                              as data_fato,
    b.fonte,
    b.ia_instalacao                                                             as instalacao,
    b.ia_sonda                                                                  as sonda,
    b.ia_poco                                                                   as poco,
    b.ia_campo                                                                  as campo,
    b.ia_bacia                                                                  as bacia,
    b.ia_municipio                                                              as municipio,
    b.ia_estado                                                                 as estado,
    b.ia_operadora_contrato                                                     as operadora_contrato,
    b.ia_operadora_inst                                                         as operadora_instalacao,
    b.dsc_empresa                                                               as empresa_siso,
    b.nom_instalacao                                                            as instalacao_siso,
    b.dat_primeira_obs                                                          as data_primeira_obs_siso,
    b.score_distancia                                                           as score_cruzamento,
    b.data_carga
from base b
left join {{ ref('dim_instalacao') }} i  on i.chave_natural = b.nome_limpo_instalacao
left join {{ ref('dim_fonte') }} f       on f.chave_natural = {{ chave_natural('b.fonte') }}
left join {{ ref('dim_localidade') }} l  on l.chave_natural = {{ chave_localidade_ia('b.ia_municipio', 'b.ia_estado', 'b.ia_bacia') }}
