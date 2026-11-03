{{ config(tags=['pos_ia']) }}

{#-
  PRATA: incidentes do SISO com as chaves de comparação prontas (maiúsculas, sem acento, só [A-Z0-9]).
  É o que o cruzamento (ouro.incidentes_cruzados) compara com o que a IA extraiu da notícia.
-#}
select
    num_incidente,
    dsc_empresa,
    nom_instalacao,
    dat_primeira_obs,
    dsc_ende_instalacao,
    dat_primeira_obs::date                                   as siso_data,
    {{ limpar_e_desacentuar('nom_instalacao') }}             as siso_nome_limpo,
    {{ limpar_e_desacentuar('dsc_ende_instalacao') }}        as siso_ende_limpo
from {{ ref('bronze_siso_incidentes') }}
