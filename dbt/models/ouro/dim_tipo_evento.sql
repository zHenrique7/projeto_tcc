{{ config(tags=['pos_ia']) }}

{#- OURO / ESTRELA: tipo do evento (Incêndio/Explosão, Vazamento, ...), lido do que a IA classificou. Chave 0 = não informado. -#}
with tipos as (
    select
        {{ chave_natural('ia_tipo_evento') }}  as chave_natural,
        min(trim(ia_tipo_evento))              as tipo_evento
    from {{ ref('prata_incidentes_ia') }}
    where {{ chave_natural('ia_tipo_evento') }} is not null
    group by 1
)

select row_number() over (order by chave_natural)::int as id_tipo_evento, chave_natural, tipo_evento
from tipos

union all

select 0, null, 'Não Informado'
