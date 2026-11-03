{{ config(materialized='table', tags=['pos_ia']) }}

{#-
  PRATA: todas as notícias que a IA já processou, uma linha por notícia, com a fonte do portal e a REGRA ÚNICA
  de "mesmo evento físico repetido em portais diferentes". As duas tabelas da ouro (incidentes_ia e
  noticias_acidentes_ia) leem daqui, então nunca divergem.

  Regra do mesmo evento: a notícia B repete a notícia A (classificada antes) quando, entre as relevantes, têm a
  mesma data do fato e o mesmo tipo de evento E (valores informados):
    - mesma instalação, OU mesma sonda, OU mesmo poço (eventos offshore e de refino); OU
    - mesmo município e mesmo estado (eventos em terra, em que cada portal cita a instalação com um nome
      diferente: "Usina Viralcool", "Usina de Pitangueiras", "Viralcool"...).
  chave_evento = id da primeira notícia do evento (seguindo a cadeia de repetições). Vale o primeiro registro
  classificado, o que mantém estáveis os alertas já enviados.

  origem = 'dedup' marca as linhas de controle gravadas pelo Python para duplicatas de título (nunca foram à IA).
  leu_materia_completa = false quando a IA só teve a manchete/resumo do RSS (captura menos confiável).
-#}
with recursive noticias as (
    select
        md5(c.titulo || '|' || c.data_publicacao::text)               as id_noticia,
        c.titulo,
        c.data_publicacao,
        n.fonte,
        c.url_noticia,
        c.fonte_texto,
        case when c.fonte_texto = 'dedup' then 'dedup' else 'ia' end  as origem,
        (c.fonte_texto not in ('rss_feed', 'dedup'))                  as leu_materia_completa,
        c.relevante,
        c.severidade,
        case when c.relevante then coalesce(c.confianca, 'não avaliada') end as confianca,
        c.motivo,
        c.tipo_evento,
        c.instalacao,
        c.sonda,
        c.poco,
        c.campo,
        c.municipio,
        c.estado,
        c.operadora_contrato,
        c.operadora_instalacao,
        c.vitimas,
        c.data_fato,
        c.classificado_em
    from {{ ref('bronze_classificacoes_ia') }} c
    left join {{ ref('bronze_noticias') }} n
           on n.titulo = c.titulo
          and n.data_publicacao = c.data_publicacao
),

relevantes as (
    select * from noticias where relevante
),

-- cada notícia relevante (b) com TODAS as anteriores (a) que descrevem o mesmo evento
repeticoes as (
    select
        b.id_noticia,
        a.id_noticia      as id_anterior,
        a.classificado_em as anterior_classificado_em,
        a.titulo          as anterior_titulo
    from relevantes b
    join relevantes a
      on a.id_noticia <> b.id_noticia
     and (a.classificado_em, a.titulo) < (b.classificado_em, b.titulo)
     and a.data_fato is not null
     and a.data_fato = b.data_fato
     and coalesce(a.tipo_evento, 'Não Informado') = coalesce(b.tipo_evento, 'Não Informado')
     and (
            (b.instalacao is not null and upper(a.instalacao) = upper(b.instalacao))
         or (b.sonda      is not null and upper(a.sonda)      = upper(b.sonda))
         or (b.poco       is not null and upper(a.poco)       = upper(b.poco))
         or (b.municipio  is not null and b.estado is not null
             and lower(unaccent(a.municipio)) = lower(unaccent(b.municipio))
             and a.estado = b.estado)
     )
),

-- para cada notícia, a ANTERIOR mais antiga que descreve o mesmo evento (a "mãe"); quem não tem mãe é a primeira do evento
mae as (
    select distinct on (id_noticia)
        id_noticia,
        id_anterior
    from repeticoes
    order by id_noticia, anterior_classificado_em, anterior_titulo
),

-- segue as mães até a primeira notícia: cobre cadeias (A repete B, B repete C, mesmo que A e C não casem direto)
raizes (id_noticia, raiz) as (
    select r.id_noticia, r.id_noticia
    from relevantes r
    where not exists (select 1 from mae m where m.id_noticia = r.id_noticia)
    union all
    select m.id_noticia, z.raiz
    from mae m
    join raizes z on z.id_noticia = m.id_anterior
),

com_evento as (
    select
        z.id_noticia,
        z.raiz                    as chave_evento,
        (z.id_noticia = z.raiz)   as primeira_noticia_do_evento
    from raizes z
)

select
    n.*,
    e.chave_evento,
    e.primeira_noticia_do_evento,
    case when n.relevante then count(*) over (partition by e.chave_evento) end as qtd_noticias_do_evento
from noticias n
left join com_evento e on e.id_noticia = n.id_noticia
