{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA - FATO: uma linha por incidente comunicado oficialmente (SISO/ANP).
  noticiado_pela_ia = true quando algum incidente detectado nas notícias foi cruzado com ele; qtd_incidentes_ia
  conta quantos. É a visão inversa do cruzamento: do que a ANP recebeu, o que a imprensa já tinha noticiado.
-#}
with cruzamentos as (
    select num_incidente_siso, count(*) as qtd_incidentes_ia
    from {{ ref('fato_incidente') }}
    where num_incidente_siso is not null
    group by num_incidente_siso
)

select
    s.num_incidente,
    {{ chave_data('s.dat_primeira_obs') }}                                      as chave_data_primeira_obs,
    coalesce(i.chave_instalacao, 0)                                             as chave_instalacao,
    s.dsc_empresa                                                               as empresa,
    s.dsc_ende_instalacao                                                       as endereco_instalacao,
    s.dat_primeira_obs,
    (x.qtd_incidentes_ia is not null)                                           as noticiado_pela_ia,
    coalesce(x.qtd_incidentes_ia, 0)                                            as qtd_incidentes_ia
from {{ ref('prata_siso_incidentes') }} s
left join {{ ref('dim_instalacao') }} i
       on i.chave_natural = s.siso_nome_limpo
left join cruzamentos x
       on x.num_incidente_siso = s.num_incidente
