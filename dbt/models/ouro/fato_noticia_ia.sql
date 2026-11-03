{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA - FATO: uma linha por notícia processada pela IA (relevantes, descartadas e duplicatas de título).
  Serve para medir a captura: quantas notícias foram lidas, quantas viraram acidente, de que fonte, com que confiança.
  Chaves numéricas para data, fonte, localidade e instalação (0 = desconhecido). Tipo de evento e severidade ficam como
  texto na própria fato (severidade_ordem ordena do mais grave ao menos grave). Título, url e motivo são atributos
  degenerados. id_incidente liga a notícia ao incidente (fato_incidente) que ela descreve; fica nulo nas notícias
  descartadas, que não são incidente. chave_evento é o hash da primeira notícia do evento, só para rastreio.
-#}
select
    c.id_noticia,
    {{ chave_data('c.data_publicacao') }}                                  as chave_data_publicacao,
    {{ chave_data('c.data_fato') }}                                        as chave_data_fato,
    coalesce(f.chave_fonte, 0)                                             as chave_fonte,
    coalesce(l.chave_localidade, 0)                                        as chave_localidade,
    coalesce(i.chave_instalacao, 0)                                        as chave_instalacao,
    coalesce(c.tipo_evento, 'Não Informado')                               as tipo_evento,
    coalesce(c.severidade, 'Não Informada')                                as severidade,
    {{ severidade_ordem('c.severidade') }}                                 as severidade_ordem,
    fi.id_incidente,
    c.chave_evento,
    c.origem,
    c.relevante,
    c.primeira_noticia_do_evento,
    c.leu_materia_completa,
    c.fonte_texto,
    c.confianca,
    coalesce(c.vitimas, 0)                                                 as vitimas,
    c.qtd_noticias_do_evento,
    (c.data_publicacao::date - c.data_fato)                                as dias_entre_fato_e_noticia,
    c.titulo,
    c.url_noticia,
    c.motivo,
    c.classificado_em
from {{ ref('prata_classificacoes_ia') }} c
left join {{ ref('prata_instalacao_ia') }} p on p.id_noticia = c.id_noticia
left join {{ ref('fato_incidente') }} fi     on fi.chave_evento = c.chave_evento
left join {{ ref('dim_instalacao') }} i      on i.chave_natural = p.dm_nome_limpo
left join {{ ref('dim_fonte') }} f           on f.chave_natural = {{ chave_natural('c.fonte') }}
left join {{ ref('dim_localidade') }} l      on l.chave_natural = {{ chave_natural_localidade('c.municipio', 'c.estado') }}
