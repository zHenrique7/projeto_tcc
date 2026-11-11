{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA - ÚNICA FATO. Grão: uma linha por INCIDENTE (evento físico) detectado pela IA nas notícias, já cruzado
  com o SISO quando houve correspondência (num_incidente_siso nulo = não encontrado no SISO). O SISO não entra como
  linhas: só como atributos do cruzamento (número, empresa, instalação e data do incidente SISO encontrado).
  Datas: data_fato, data_publicacao e data_siso são DATAS (colunas legíveis); a ligação com dim_data é pelo id sequencial
  id_data_fato / id_data_publicacao / id_data_siso (3 papéis; 0 = sem data). Data do fato = a mais antiga informada pelas
  notícias do evento; sem ela, a publicação mais antiga.
  Instalação (dim_instalacao, 2 papéis): id_instalacao (onde ocorreu: tradução oficial > SISO > texto da IA) e
  id_instalacao_siso (instalação do incidente SISO cruzado). Empresas (dim_empresa, 3 papéis): contrato, instalação, SISO.
  Fonte, local, tipo, severidade e status ficam nas dimensões. Medidas: qtd_incidente, vitimas, qtd_noticias_do_evento,
  confianca, score_cruzamento. Degenerados: id_incidente, num_incidente_siso, título, url, motivo, sonda, poço, campo e, para conferir o cruzamento,
  data_primeira_obs_siso (data e hora), instalacao_siso, endereco_instalacao_siso e descricao_incidente_siso do incidente SISO encontrado.
-#}
with base as (
    select
        c.*,
        coalesce(
            c.instalacao_dm_limpa,
            case when c.status_cruzamento in ('Match Perfeito', 'Match por Substring')
                 then nullif({{ limpar_e_desacentuar('c.nom_instalacao') }}, '') end,
            nullif(nullif(c.instalacao_chave_busca, ''), 'NAOINFORMADO')
        )                                                                       as nk_instalacao,
        case when c.num_incidente is not null
             then nullif({{ limpar_e_desacentuar('c.nom_instalacao') }}, '') end as nk_instalacao_siso
    from {{ ref('prata_incidentes_cruzados') }} c
)

select
    b.id_incidente,
    b.num_incidente                                                             as num_incidente_siso,
    b.ia_data_conv                                                              as data_fato,
    b.data_publicacao::date                                                     as data_publicacao,
    b.dat_primeira_obs::date                                                    as data_siso,
    coalesce(df.id_data, 0)                                                     as id_data_fato,
    coalesce(dp.id_data, 0)                                                     as id_data_publicacao,
    coalesce(ds.id_data, 0)                                                     as id_data_siso,
    coalesce(f.id_fonte, 0)                                                     as id_fonte,
    coalesce(l.id_localidade, 0)                                                as id_localidade,
    coalesce(i.id_instalacao, 0)                                                as id_instalacao,
    coalesce(isiso.id_instalacao, 0)                                            as id_instalacao_siso,
    coalesce(ec.id_empresa, 0)                                                  as id_empresa_contrato,
    coalesce(ei.id_empresa, 0)                                                  as id_empresa_instalacao,
    coalesce(es.id_empresa, 0)                                                  as id_empresa_siso,
    coalesce(t.id_tipo_evento, 0)                                               as id_tipo_evento,
    coalesce(sv.id_severidade, 0)                                               as id_severidade,
    coalesce(st.id_status_cruzamento, 0)                                        as id_status_cruzamento,
    1                                                                           as qtd_incidente,
    b.ia_vitimas                                                                as vitimas,
    b.qtd_noticias_do_evento,
    b.ia_confianca                                                              as confianca,
    b.score_distancia                                                           as score_cruzamento,
    b.titulo,
    b.url_noticia,
    b.ia_motivo                                                                 as motivo,
    b.ia_sonda                                                                  as sonda,
    b.ia_poco                                                                   as poco,
    b.ia_campo                                                                  as campo,
    b.dat_primeira_obs                                                          as data_primeira_obs_siso,
    b.nom_instalacao                                                            as instalacao_siso,
    b.dsc_ende_instalacao                                                       as endereco_instalacao_siso,
    b.dsc_incidente                                                             as descricao_incidente_siso,
    b.data_carga
from base b
left join {{ ref('dim_data') }} df               on df.data = b.ia_data_conv
left join {{ ref('dim_data') }} dp               on dp.data = b.data_publicacao::date
left join {{ ref('dim_data') }} ds               on ds.data = b.dat_primeira_obs::date
left join {{ ref('dim_fonte') }} f               on f.chave_natural = {{ chave_natural('b.fonte') }}
left join {{ ref('dim_localidade') }} l          on l.chave_natural = {{ chave_localidade_ia('b.ia_municipio', 'b.ia_estado', 'b.ia_bacia') }}
left join {{ ref('dim_instalacao') }} i          on i.chave_natural = b.nk_instalacao
left join {{ ref('dim_instalacao') }} isiso      on isiso.chave_natural = b.nk_instalacao_siso
left join {{ ref('dim_empresa') }} ec            on ec.chave_natural = {{ chave_natural('b.ia_operadora_contrato') }}
left join {{ ref('dim_empresa') }} ei            on ei.chave_natural = {{ chave_natural('b.ia_operadora_inst') }}
left join {{ ref('dim_empresa') }} es            on es.chave_natural = {{ chave_natural('b.dsc_empresa') }}
left join {{ ref('dim_tipo_evento') }} t         on t.chave_natural = {{ chave_natural('b.ia_tipo_evento') }}
left join {{ ref('dim_severidade') }} sv         on sv.severidade = upper(trim(b.ia_severidade))
left join {{ ref('dim_status_cruzamento') }} st  on st.status_cruzamento = b.status_cruzamento
