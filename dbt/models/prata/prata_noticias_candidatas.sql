{{ config(materialized='table', tags=['pre_ia']) }}

{#- Fila de entrada da IA: só as notícias admitidas pelo pré-filtro.
    `prioridade` (= pontuação) é a coluna que o classify.py usa para ordenar: a cota da Groq é gasta
    primeiro com o que mais parece incidente real de P&G. -#}
select
    titulo, data_publicacao, fonte, resumo_html, url_noticia,
    pontuacao as prioridade,
    pontuacao, hits_forte, hits_fraco, ctx_forte, ctx_fraco, ctx_fonte
from {{ ref('prata_noticias_pontuadas') }}
where admitida
order by pontuacao desc, data_publicacao desc
