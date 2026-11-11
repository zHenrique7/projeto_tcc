{{ config(tags=['pos_ia']) }}

{#- OURO / ESTRELA: severidade do incidente. `ordem` ordena do mais grave (1) ao menos grave (5). Chave 0 = não informada. -#}
select * from (
    values
        (1, 'CRÍTICO',       1),
        (2, 'ALTO',          2),
        (3, 'MÉDIO',         3),
        (4, 'INFORMATIVO',   4),
        (0, 'Não Informada', 5)
) as v(id_severidade, severidade, ordem)
