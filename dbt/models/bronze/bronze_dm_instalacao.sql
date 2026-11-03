{{ config(tags=['pos_ia']) }}

{#- BRONZE: espelho 1:1 de raw.dm_ssm_wbs_instalacao (nome e sigla oficiais das instalações). -#}
select
    nom_identificacao,
    sig_instalacao
from {{ source('raw', 'dm_ssm_wbs_instalacao') }}
