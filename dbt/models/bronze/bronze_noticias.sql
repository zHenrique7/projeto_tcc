{{ config(tags=['pre_ia', 'pos_ia']) }}

{#-
  BRONZE: espelho 1:1 de raw.noticias (a coleta feita pelo Python). Sem filtro e sem regra de negócio:
  só nomeia as colunas que as camadas seguintes usam. Tags nas duas fases porque a prata (pre_ia) e a ouro (pos_ia) leem daqui.
-#}
select
    titulo,
    data_publicacao,
    fonte,
    resumo_html,
    url_noticia,
    url_fonte,
    coletado_em
from {{ source('raw', 'noticias') }}
