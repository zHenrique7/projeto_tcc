{{ config(tags=['pre_ia', 'pos_ia']) }}

{#-
  BRONZE: espelho 1:1 de raw.classificacoes_ia (uma linha por notícia processada pela IA, relevante ou não, e também
  as linhas de controle com fonte_texto = 'dedup'). Sem regra de negócio. É a ÚNICA porta de entrada dessa tabela
  no dbt: a prata e a ouro nunca leem raw.classificacoes_ia direto.
-#}
select
    titulo,
    data_publicacao,
    url_noticia,
    fonte_texto,
    relevante,
    severidade,
    confianca,
    motivo,
    tipo_evento,
    sonda,
    instalacao,
    poco,
    campo,
    municipio,
    estado,
    operadora_contrato,
    operadora_instalacao,
    vitimas,
    data_fato,
    classificado_em
from {{ source('raw', 'classificacoes_ia') }}
