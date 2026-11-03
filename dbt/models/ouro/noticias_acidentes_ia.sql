{{ config(materialized='table', tags=['pos_ia']) }}

{#-
  OURO: tabela de acompanhamento. TODA notícia que a IA classificou como acidente/incidente operacional, uma linha por
  notícia, para medir o que o agente está capturando.

  Diferença para ouro.incidentes_ia: aquela tabela traz um registro por EVENTO (base dos alertas); esta mantém TODAS
  as notícias e só sinaliza a repetição (regra única, definida em prata_classificacoes_ia):
    chave_evento              : id da primeira notícia do evento
    primeira_noticia_do_evento: true na primeira notícia classificada daquele evento
    qtd_noticias_do_evento    : quantos portais/notícias cobriram o mesmo evento
  leu_materia_completa = false quando a IA só teve a manchete/resumo do RSS (captura menos confiável).
  confianca: alta | média | baixa; linhas anteriores a esse campo ficam como 'não avaliada'.
-#}
select
    id_noticia,
    data_publicacao,
    data_fato,
    (data_publicacao::date - data_fato)   as dias_entre_fato_e_noticia,
    fonte,
    titulo,
    url_noticia,
    severidade,
    confianca,
    tipo_evento,
    instalacao,
    sonda,
    poco,
    campo,
    municipio,
    estado,
    operadora_contrato,
    operadora_instalacao,
    vitimas,
    motivo,
    fonte_texto,
    leu_materia_completa,
    chave_evento,
    primeira_noticia_do_evento,
    qtd_noticias_do_evento,
    classificado_em
from {{ ref('prata_classificacoes_ia') }}
where relevante
order by data_publicacao desc
