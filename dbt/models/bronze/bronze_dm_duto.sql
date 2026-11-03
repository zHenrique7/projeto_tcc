{{ config(tags=['pos_ia']) }}

{#- BRONZE: espelho 1:1 de raw.dm_ssm_wbs_duto (nome oficial dos dutos). -#}
select
    nom_instalacao
from {{ source('raw', 'dm_ssm_wbs_duto') }}
