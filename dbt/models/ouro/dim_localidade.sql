{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA: localidade dos incidentes. Uma linha por município+estado (eventos em terra) ou por BACIA
  (eventos offshore sem município); sem nenhum dos dois, por estado. Chave 0 = localidade desconhecida.
  Parte dos dados consolidados do evento (prata_classificacoes_ia.*_evento), com a UF já corrigida pela bacia
  (Foz do Amazonas = AP, nunca AM) e a bacia normalizada ("Foz do Amazonas" e "Margem Equatorial" são uma só),
  então as várias grafias do mesmo lugar caem na mesma chave.
  tipo_localidade: Município | Bacia | Estado.
-#}
with locais as (
    select
        {{ chave_localidade_ia('municipio_evento', 'estado_evento', 'bacia_evento') }}  as chave_natural,
        municipio_evento                                                                 as municipio,
        estado_evento                                                                    as estado,
        bacia_evento                                                                     as bacia
    from {{ ref('prata_classificacoes_ia') }}
    where relevante
      and primeira_noticia_do_evento
),

agrupadas as (
    select
        chave_natural,
        min(trim(municipio))                                                       as municipio,
        case when chave_natural like 'bacia:%' then 'Offshore'
             when count(distinct upper(trim(estado))) = 1 then min(upper(trim(estado))) end as estado,
        min(bacia)                                                                 as bacia
    from locais
    where chave_natural is not null
    group by 1
)

select
    row_number() over (order by chave_natural)::int      as chave_localidade,
    chave_natural,
    coalesce(municipio, 'Não Informado')                 as municipio,
    coalesce(estado, 'Não Informado')                    as estado,
    coalesce(bacia, 'Não Informada')                     as bacia,
    case when chave_natural like 'bacia:%' then 'Bacia'
         when municipio is not null        then 'Município'
         else 'Estado' end                               as tipo_localidade
from agrupadas

union all

select 0, null, 'Não Informado', 'Não Informado', 'Não Informada', 'Não Informada'
