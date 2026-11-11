{{ config(tags=['pos_ia']) }}

{#-
  OURO / ESTRELA: resultado do cruzamento do incidente detectado pela IA com o SISO. Os textos são os que o cruzamento
  (prata_incidentes_cruzados) grava. comunicado_siso = o incidente foi encontrado no SISO.
-#}
select * from (
    values
        (1, 'Match Perfeito',                          1, true,  'Comunicado ao SISO'),
        (2, 'Match por Substring',                     2, true,  'Comunicado ao SISO'),
        (3, 'Match por Localidade (Fallback)',         3, true,  'Comunicado ao SISO'),
        (4, 'Nao Comunicado / Sem Correspondencia',    4, false, 'Não comunicado'),
        (0, 'Não Informado',                           5, false, 'Sem classificação')
) as v(id_status_cruzamento, status_cruzamento, ordem, comunicado_siso, grupo)
