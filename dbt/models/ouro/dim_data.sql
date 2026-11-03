{{ config(tags=['pos_ia']) }}

{#- OURO / ESTRELA: dimensão de datas (2015 até um ano à frente) + membro desconhecido 1900-01-01. -#}
select
    d::date                                                   as chave_data,
    extract(year from d)::int                                 as ano,
    extract(quarter from d)::int                              as trimestre,
    extract(month from d)::int                                as mes,
    (array['janeiro','fevereiro','março','abril','maio','junho','julho','agosto',
           'setembro','outubro','novembro','dezembro'])[extract(month from d)::int] as nome_mes,
    to_char(d, 'YYYY-MM')                                     as ano_mes,
    extract(isodow from d)::int                               as dia_semana_num,
    (array['segunda','terça','quarta','quinta','sexta','sábado','domingo'])[extract(isodow from d)::int] as dia_semana,
    extract(week from d)::int                                 as semana_ano
from generate_series(date '2015-01-01', current_date + 365, interval '1 day') as g(d)

union all

select date '1900-01-01', null, null, null, 'Não informada', 'Não informada', null, 'Não informado', null
