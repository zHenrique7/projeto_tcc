{{ config(tags=['pos_ia']) }}

{#-
  OURO: incidentes aprovados pela IA, UM POR EVENTO FÍSICO (equivale à tabela INCIDENTES_IA do Fabric).
  É a base dos alertas e do cruzamento com o SISO. A regra de "mesmo evento" fica em prata_classificacoes_ia;
  aqui só se escolhe a primeira notícia de cada evento e se formata para consumo (valores ausentes viram 'Não Informado').
-#}
select distinct on (c.titulo)
    c.chave_evento,
    c.data_publicacao,
    c.fonte,
    c.titulo,
    c.url_noticia,
    true                                                  as ia_relevante,
    c.severidade                                          as ia_severidade,
    c.confianca                                           as ia_confianca,
    coalesce(c.tipo_evento, 'Não Informado')              as ia_tipo_evento,
    coalesce(c.instalacao, 'Não Informado')               as ia_instalacao,
    coalesce(c.sonda, 'Não Informado')                    as ia_sonda,
    coalesce(c.poco, 'Não Informado')                     as ia_poco,
    coalesce(c.campo, 'Não Informado')                    as ia_campo,
    coalesce(c.municipio, 'Não Informado')                as ia_municipio,
    coalesce(c.estado, 'Não Informado')                   as ia_estado,
    coalesce(c.operadora_contrato, 'Não Informado')       as ia_operadora_contrato,
    coalesce(c.operadora_instalacao, 'Não Informado')     as ia_operadora_inst,
    coalesce(c.vitimas, 0)                                as ia_vitimas,
    c.data_fato                                           as ia_data_fato,
    coalesce(c.motivo, 'Não Informado')                   as ia_motivo,
    c.qtd_noticias_do_evento,
    c.classificado_em                                     as data_carga
from {{ ref('prata_classificacoes_ia') }} c
where c.relevante
  and c.primeira_noticia_do_evento
order by c.titulo, c.classificado_em
