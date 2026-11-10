{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA - FATO: uma linha por notícia processada pela IA (relevantes, descartadas e duplicatas de título).
  Serve para medir a captura: quantas notícias foram lidas, quantas viraram acidente, de que fonte, com que confiança.
  Chaves numéricas para data, fonte, localidade e instalação (0 = desconhecido). Tipo de evento e severidade ficam como
  texto na própria fato (severidade_ordem ordena do mais grave ao menos grave). Título, url e motivo são atributos
  degenerados. Absorveu a antiga noticias_acidentes_ia: traz o texto extraído de cada notícia (instalação, sonda, poço,
  campo, bacia, município, estado, operadoras), então basta filtrar relevante = true para ver só os acidentes. id_incidente liga a notícia ao incidente (fato_incidente) que ela descreve; fica nulo nas notícias
  descartadas, que não são incidente. id_noticia é numérico (1, 2, 3...); os hashes usados para agrupar ficam só na prata.
-#}
select
    row_number() over (order by c.classificado_em, c.titulo, c.data_publicacao)::int as id_noticia,
    {{ chave_data('c.data_publicacao') }}                                  as chave_data_publicacao,
    {{ chave_data('coalesce(c.data_fato_evento, c.data_fato, c.data_ref_evento)') }} as chave_data_fato,
    coalesce(f.chave_fonte, 0)                                             as chave_fonte,
    coalesce(l.chave_localidade, 0)                                        as chave_localidade,
    coalesce(i.chave_instalacao, 0)                                        as chave_instalacao,
    coalesce(c.tipo_evento, 'Não Informado')                               as tipo_evento,
    coalesce(c.severidade, 'Não Informada')                                as severidade,
    {{ severidade_ordem('c.severidade') }}                                 as severidade_ordem,
    fi.id_incidente,
    c.origem,
    c.relevante,
    c.primeira_noticia_do_evento,
    c.leu_materia_completa,
    c.fonte_texto,
    c.confianca,
    c.vitimas                                                              as vitimas,  -- NULL = não informado
    c.qtd_noticias_do_evento,
    (c.data_publicacao::date - c.data_fato)                                as dias_entre_fato_e_noticia,
    c.titulo,
    c.url_noticia,
    c.motivo,
    -- texto como a IA extraiu de CADA notícia (acompanhamento da captura; os do evento consolidado estão em fato_incidente)
    c.data_publicacao,
    c.data_fato,
    c.fonte,
    c.instalacao,
    c.sonda,
    c.poco,
    c.campo,
    c.bacia,
    c.municipio,
    c.estado_normalizado                                                   as estado,
    c.operadora_contrato,
    c.operadora_instalacao,
    c.classificado_em
from {{ ref('prata_classificacoes_ia') }} c
left join {{ ref('prata_instalacao_ia') }} p on p.id_noticia = c.id_noticia
left join {{ ref('prata_incidentes_cruzados') }} fi on fi.chave_evento = c.chave_evento
left join {{ ref('dim_instalacao') }} i      on i.chave_natural = coalesce(p.dm_nome_limpo, nullif(nullif(p.ia_chave_busca, ''), 'NAOINFORMADO'))
left join {{ ref('dim_fonte') }} f           on f.chave_natural = {{ chave_natural('c.fonte') }}
left join {{ ref('dim_localidade') }} l      on l.chave_natural = {{ chave_localidade_ia('coalesce(c.municipio_evento, c.municipio)', 'coalesce(c.estado_evento, c.estado_normalizado)', 'coalesce(c.bacia_evento, c.bacia)') }}
