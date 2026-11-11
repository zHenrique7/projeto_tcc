{{ config(tags=['pos_ia']) }}

{#-
  PRATA (fora da estrela): uma linha por notícia processada pela IA (relevantes, descartadas e duplicatas de título).
  Era a antiga ouro.fato_noticia_ia; saiu do modelo estrela porque o grão é a notícia, não o incidente. Serve para
  acompanhar a captura (quantas lidas, quantas viraram incidente, por fonte, com que confiança) e para auditoria.
  id_incidente liga a notícia ao incidente de ouro.fato_incidente (nulo nas descartadas).
-#}
select
    c.id_noticia,
    fi.id_incidente,
    c.origem,
    c.relevante,
    c.primeira_noticia_do_evento,
    c.leu_materia_completa,
    c.fonte_texto,
    c.confianca,
    c.vitimas,
    c.qtd_noticias_do_evento,
    (c.data_publicacao::date - c.data_fato)                  as dias_entre_fato_e_noticia,
    c.titulo,
    c.url_noticia,
    c.motivo,
    c.data_publicacao,
    c.data_fato,
    c.data_fato_evento,
    c.fonte,
    c.tipo_evento,
    c.severidade,
    c.instalacao,
    c.sonda,
    c.poco,
    c.campo,
    c.bacia,
    c.municipio,
    c.estado_normalizado                                     as estado,
    c.operadora_contrato,
    c.operadora_instalacao,
    c.classificado_em
from {{ ref('prata_classificacoes_ia') }} c
left join {{ ref('prata_incidentes_cruzados') }} fi on fi.chave_evento = c.chave_evento
