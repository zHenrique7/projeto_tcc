{{ config(tags=['pos_ia']) }}

{#-
  PRATA: incidentes aprovados pela IA, UM POR EVENTO FÍSICO (equivale à tabela INCIDENTES_IA do Fabric).
  É a base do cruzamento com o SISO (prata_incidentes_cruzados). Tabela intermediária: o consumo (Power BI e alertas) é
  feito em ouro.fato_incidente, que traz todas as colunas daqui e do cruzamento. A regra de "mesmo evento" fica em prata_classificacoes_ia;
  aqui só se escolhe a primeira notícia de cada evento (que dá título, url e fonte) e se formata para consumo (valores
  ausentes viram 'Não Informado'). Tipo, severidade, data do fato, ativo, local e vítimas vêm CONSOLIDADOS do evento
  (colunas *_evento): o melhor valor entre todas as notícias, não só o da primeira.
-#}
select distinct on (c.titulo)
    c.chave_evento,
    c.data_publicacao,
    c.fonte,
    c.titulo,
    c.url_noticia,
    true                                                  as ia_relevante,
    coalesce(c.severidade_evento, c.severidade)           as ia_severidade,
    c.confianca                                           as ia_confianca,
    coalesce(c.tipo_evento_evento, c.tipo_evento, 'Não Informado')  as ia_tipo_evento,
    coalesce(c.instalacao_evento, 'Não Informado')        as ia_instalacao,
    coalesce(c.sonda_evento, 'Não Informado')             as ia_sonda,
    coalesce(c.poco_evento, 'Não Informado')              as ia_poco,
    coalesce(c.campo_evento, 'Não Informado')             as ia_campo,
    coalesce(c.bacia_evento, 'Não Informado')             as ia_bacia,
    coalesce(c.municipio_evento, 'Não Informado')         as ia_municipio,
    coalesce(c.estado_evento, 'Não Informado')            as ia_estado,
    coalesce(c.operadora_contrato_evento, 'Não Informado') as ia_operadora_contrato,
    coalesce(c.operadora_instalacao_evento, 'Não Informado') as ia_operadora_inst,
    c.vitimas_evento                                      as ia_vitimas,  -- NULL = não informado (0 seria "nenhuma vítima")
    c.data_fato_evento                                    as ia_data_fato,
    c.data_ref_evento                                     as ia_data_ref,
    coalesce(c.motivo, 'Não Informado')                   as ia_motivo,
    c.qtd_noticias_do_evento,
    c.classificado_em                                     as data_carga
from {{ ref('prata_classificacoes_ia') }} c
where c.relevante
  and c.primeira_noticia_do_evento
order by c.titulo, c.classificado_em
