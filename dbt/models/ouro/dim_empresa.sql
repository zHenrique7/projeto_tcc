{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA: empresas (operadora do contrato, operadora da instalação e empresa que comunicou ao SISO). Uma só
  dimensão com três papéis na fato (id_empresa_contrato, id_empresa_instalacao, id_empresa_siso). A chave
  natural é o nome normalizado (minúsculas, sem acento); grafias realmente diferentes continuam sendo empresas distintas.
-#}
with nomes as (
    select ia_operadora_contrato as nome from {{ ref('prata_incidentes_cruzados') }}
    union all
    select ia_operadora_inst     from {{ ref('prata_incidentes_cruzados') }}
    union all
    select dsc_empresa           from {{ ref('prata_incidentes_cruzados') }}
),

empresas as (
    select
        {{ chave_natural('nome') }}  as chave_natural,
        min(trim(nome))              as empresa
    from nomes
    where {{ chave_natural('nome') }} is not null
    group by 1
)

select row_number() over (order by chave_natural)::int as id_empresa, chave_natural, empresa
from empresas

union all

select 0, null, 'Não Informada'
