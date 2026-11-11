{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA: dimensão de datas (2015 até um ano à frente) + membro desconhecido (id 0, data 1900-01-01).
  id_data é um inteiro sequencial (1, 2, 3...) sem significado de data; `data` é a data de verdade (marcar esta coluna
  como tabela de datas no Power BI). A fato liga por id_data_* e também traz as datas em colunas próprias.
-#}
with datas as (
    select d::date as data
    from generate_series(date '2015-01-01', current_date + 365, interval '1 day') as g(d)
)

select
    row_number() over (order by data)::int                    as id_data,
    data,
    extract(year from data)::int                              as ano,
    extract(quarter from data)::int                           as trimestre,
    extract(month from data)::int                             as mes,
    (array['janeiro','fevereiro','março','abril','maio','junho','julho','agosto',
           'setembro','outubro','novembro','dezembro'])[extract(month from data)::int] as nome_mes,
    to_char(data, 'YYYY-MM')                                  as ano_mes,
    extract(isodow from data)::int                            as dia_semana_num,
    (array['segunda','terça','quarta','quinta','sexta','sábado','domingo'])[extract(isodow from data)::int] as dia_semana,
    extract(week from data)::int                              as semana_ano
from datas

union all

select 0, date '1900-01-01', null, null, null, 'Não informada', 'Não informada', null, 'Não informado', null
