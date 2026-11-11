{{ config(tags=['pos_ia']) }}

{#- BRONZE: espelho 1:1 de raw.siso_incidentes (CSV da ANP carregado pelo Python). A limpeza está em prata_siso_incidentes. -#}
select
    num_incidente,
    dsc_empresa,
    nom_instalacao,
    dat_primeira_obs,
    dsc_ende_instalacao,
    dsc_incidente
from {{ source('raw', 'siso_incidentes') }}
