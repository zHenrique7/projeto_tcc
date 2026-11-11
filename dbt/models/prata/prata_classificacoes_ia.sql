{{ config(materialized='table', tags=['pos_ia']) }}

{#-
  PRATA: todas as notícias que a IA já processou, uma linha por notícia, com a fonte do portal, a REGRA ÚNICA de
  "mesmo evento físico repetido em portais diferentes" e os dados CONSOLIDADOS por evento. As tabelas da ouro
  (prata_incidentes_ia, dimensões e fatos) leem daqui, então nunca divergem.

  REGRA DO MESMO EVENTO. A notícia B repete a notícia A (classificada antes) quando as duas são relevantes, têm
  tipos de evento compatíveis e se enquadram em UMA das regras abaixo (data de referência = data do fato; sem ela,
  a de publicação):
    R1 ativo      : mesmo ativo (instalação, sonda ou poço, comparados pela chave_ativo: "FPSO P-40" = "P-40",
                    "Skandy Logger" = "Skandi Logger") e datas de referência a até 5 dias; se uma das duas notícias
                    não informa a data do fato (acompanhamento), a janela sobe para 45 dias;
    R2 bacia      : mesma bacia normalizada ("Foz do Amazonas", "Margem Equatorial" e "Amapá" são a mesma região),
                    datas a até 7 dias (45 se faltar a data do fato) e UMA das duas sem ativo identificado. Nas bacias
                    de var('bacias_evento_unico') (campanha exploratória única, como a Foz do Amazonas, onde a sonda,
                    o poço e o bloco são o mesmo incidente) vale mesmo com ativos diferentes;
    R3 município  : mesmo município e estado (eventos em terra, em que cada portal cita o ativo com um nome) e
                    datas a até 1 dia;
    R4 estado     : uma das duas sem ativo E sem município (matéria vaga: "refinaria da Petrobras em Minas"), mesmo
                    estado, mesmo grupo de tipo (sem coringa) e datas do fato a até 1 dia.
  Tipos compatíveis: o mesmo grupo (Incêndio/Explosão; Acidente/Fatalidade; Vazamento) ou qualquer par em que um dos
  lados seja uma CONSEQUÊNCIA ou um tipo genérico (Shutdown, Evacuação, Acidente, não informado). É o que junta
  "Incidente paralisa a Reduc" (Shutdown) com "princípio de incêndio na Reduc" (Incêndio).
  chave_evento = id da primeira notícia do evento (seguindo a cadeia de repetições). Vale o primeiro registro
  classificado, o que mantém estáveis os alertas já enviados.

  DADOS DO EVENTO (colunas *_evento, iguais em todas as notícias do mesmo evento): como cada portal informa um pedaço
  (um traz a sonda, outro o município, outro a severidade mais grave), o evento usa o melhor valor entre elas:
    data_fato_evento   : a MAIS ANTIGA data de fato informada (matérias de acompanhamento não deslocam o evento);
    data_ref_evento    : data_fato_evento ou, sem ela, a publicação mais antiga do evento;
    tipo_evento_evento : o tipo de maior prioridade (Fatalidade > Explosão > Incêndio > Vazamento > Acidente >
                         Evacuação > Shutdown), porque parada e evacuação são consequência do fato;
    severidade_evento  : a MAIS GRAVE entre as notícias (critério de precaução para alertas);
    instalação, sonda, poço, campo, bacia, operadoras e vítimas: primeiro valor informado (vítimas: o maior);
    município/estado   : do mesmo registro (o primeiro que informa município), com a UF corrigida pela bacia.

  origem = 'dedup' marca as linhas de controle gravadas pelo Python para duplicatas de título (nunca foram à IA).
  origem = 'data_inconsistente' marca matérias antigas que o feed datou como novas (descartadas pelo Python pela data da URL, sem IA).
  leu_materia_completa = false quando a IA só teve a manchete/resumo do RSS (captura menos confiável).
-#}
{% set janela_ativo       = var('janela_evento_ativo_dias', 5) | int %}
{% set bacias_unico       = var('bacias_evento_unico', ['Foz do Amazonas']) %}
{% set janela_bacia       = var('janela_evento_bacia_dias', 7) | int %}
{% set janela_sem_data    = var('janela_evento_sem_data_dias', 45) | int %}

with recursive noticias as (
    select
        md5(c.titulo || '|' || c.data_publicacao::text)               as id_noticia,
        c.titulo,
        c.data_publicacao,
        n.fonte,
        c.url_noticia,
        c.fonte_texto,
        case when c.fonte_texto in ('dedup', 'data_inconsistente') then c.fonte_texto else 'ia' end as origem,
        (c.fonte_texto not in ('rss_feed', 'dedup', 'data_inconsistente')) as leu_materia_completa,
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

-- normalizações usadas na comparação e nas dimensões (só das relevantes; as demais ficam nulas)
enriquecidas as (
    select
        n.*,
        coalesce(
            {{ bacia_normalizada('n.campo') }},
            {{ bacia_normalizada("coalesce(n.titulo, '') || ' ' || coalesce(n.motivo, '')") }}
        )                                                                         as bacia
    from noticias n
),

normalizadas as (
    select
        e.*,
        {{ estado_corrigido('e.estado', 'e.bacia') }}                             as estado_corr,
        coalesce(e.data_fato, e.data_publicacao::date)                            as data_ref,
        (e.data_fato is not null)                                                 as tem_data_fato,
        -- chaves de ativo válidas (>= 3 caracteres, não "NAOINFORMADO"); vazio quando a notícia não identifica o ativo
        array_remove(array[
            case when length({{ chave_ativo('e.instalacao') }}) >= 3
                  and {{ chave_ativo('e.instalacao') }} <> 'NAOINFORMADO' then {{ chave_ativo('e.instalacao') }} end,
            case when length({{ chave_ativo('e.sonda') }}) >= 3
                  and {{ chave_ativo('e.sonda') }} <> 'NAOINFORMADO' then {{ chave_ativo('e.sonda') }} end,
            case when length({{ chave_ativo('e.poco') }}) >= 3
                  and {{ chave_ativo('e.poco') }} <> 'NAOINFORMADO' then {{ chave_ativo('e.poco') }} end
        ], null)                                                                  as ativos,
        case
            when e.tipo_evento in ('Incêndio', 'Explosão')       then 'fogo'
            when e.tipo_evento in ('Acidente', 'Fatalidade')     then 'acidente'
            when e.tipo_evento = 'Vazamento'                     then 'vazamento'
            else 'outro'
        end                                                                       as grupo_tipo,
        (coalesce(e.tipo_evento, 'Não Informado') in ('Shutdown', 'Evacuação', 'Acidente', 'Não Informado')) as tipo_generico,
        lower(unaccent(trim(e.municipio)))                                        as municipio_n
    from enriquecidas e
),

relevantes as (
    select * from normalizadas where relevante
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
     -- tipos compatíveis
     and (
            a.grupo_tipo = b.grupo_tipo and a.grupo_tipo <> 'outro'
         or coalesce(a.tipo_evento, 'Não Informado') = coalesce(b.tipo_evento, 'Não Informado')
         or a.tipo_generico
         or b.tipo_generico
     )
     and (
            -- R1: mesmo ativo
            (
                a.ativos && b.ativos
                and abs(a.data_ref - b.data_ref) <= case when a.tem_data_fato and b.tem_data_fato
                                                         then {{ janela_ativo }} else {{ janela_sem_data }} end
            )
            -- R2: um dos lados sem ativo identificado, mesma bacia
         or (
                a.bacia is not null and a.bacia = b.bacia
                and (cardinality(a.ativos) = 0 or cardinality(b.ativos) = 0
                     or a.bacia in ({% for x in bacias_unico %}'{{ x }}'{% if not loop.last %}, {% endif %}{% endfor %}))
                and abs(a.data_ref - b.data_ref) <= case when a.tem_data_fato and b.tem_data_fato
                                                         then {{ janela_bacia }} else {{ janela_sem_data }} end
            )
            -- R3: mesmo município e estado (eventos em terra)
         or (
                b.municipio_n is not null and b.estado_corr is not null
                and a.municipio_n = b.municipio_n
                and a.estado_corr = b.estado_corr
                and abs(a.data_ref - b.data_ref) <= 1
            )
            -- R4: matéria vaga (sem ativo e sem município) do mesmo estado, mesmo grupo de tipo, datas do fato a até 1 dia
         or (
                b.estado_corr is not null and a.estado_corr = b.estado_corr
                and a.grupo_tipo = b.grupo_tipo and a.grupo_tipo <> 'outro'
                and a.tem_data_fato and b.tem_data_fato
                and abs(a.data_ref - b.data_ref) <= 1
                and (
                       (cardinality(b.ativos) = 0 and b.municipio_n is null)
                    or (cardinality(a.ativos) = 0 and a.municipio_n is null)
                )
            )
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
),

-- dados consolidados por evento (ver "DADOS DO EVENTO" no cabeçalho)
evento as (
    select
        e.chave_evento,
        min(r.data_fato)                                                                             as data_fato_evento,
        min(r.data_publicacao::date)                                                                 as data_pub_evento,
        (array_agg(r.tipo_evento order by {{ tipo_evento_prioridade('r.tipo_evento') }}, r.classificado_em, r.titulo)
            filter (where r.tipo_evento is not null))[1]                                             as tipo_evento_evento,
        min({{ severidade_ordem('r.severidade') }})                                                  as severidade_ordem_evento,
        max(r.vitimas)                                                                               as vitimas_evento,
        (array_agg(r.instalacao order by r.classificado_em, r.titulo) filter (where r.instalacao is not null))[1] as instalacao_evento,
        (array_agg(r.sonda order by r.classificado_em, r.titulo)      filter (where r.sonda is not null))[1]      as sonda_evento,
        (array_agg(r.poco order by r.classificado_em, r.titulo)       filter (where r.poco is not null))[1]       as poco_evento,
        (array_agg(r.campo order by r.classificado_em, r.titulo)      filter (where r.campo is not null))[1]      as campo_evento,
        (array_agg(r.bacia order by r.classificado_em, r.titulo)      filter (where r.bacia is not null))[1]      as bacia_evento,
        (array_agg(r.operadora_contrato order by r.classificado_em, r.titulo)   filter (where r.operadora_contrato is not null))[1]   as operadora_contrato_evento,
        (array_agg(r.operadora_instalacao order by r.classificado_em, r.titulo) filter (where r.operadora_instalacao is not null))[1] as operadora_instalacao_evento,
        -- município e estado do MESMO registro (o primeiro que informa município); sem município, o primeiro estado
        (array_agg(r.municipio order by r.classificado_em, r.titulo)  filter (where r.municipio is not null))[1]  as municipio_evento,
        coalesce(
            (array_agg(r.estado_corr order by r.classificado_em, r.titulo) filter (where r.municipio is not null and r.estado_corr is not null))[1],
            (array_agg(r.estado_corr order by r.classificado_em, r.titulo) filter (where r.estado_corr is not null))[1]
        )                                                                                            as estado_evento
    from com_evento e
    join relevantes r on r.id_noticia = e.id_noticia
    group by e.chave_evento
)

select
    n.id_noticia, n.titulo, n.data_publicacao, n.fonte, n.url_noticia, n.fonte_texto, n.origem, n.leu_materia_completa,
    n.relevante, n.severidade, n.confianca, n.motivo, n.tipo_evento, n.instalacao, n.sonda, n.poco, n.campo,
    n.municipio, n.estado, n.operadora_contrato, n.operadora_instalacao, n.vitimas, n.data_fato, n.classificado_em,
    n.bacia,
    n.estado_corr                                                                  as estado_normalizado,
    ce.chave_evento,
    ce.primeira_noticia_do_evento,
    case when n.relevante then count(*) over (partition by ce.chave_evento) end    as qtd_noticias_do_evento,
    ev.data_fato_evento,
    coalesce(ev.data_fato_evento, ev.data_pub_evento)                              as data_ref_evento,
    ev.tipo_evento_evento,
    case ev.severidade_ordem_evento when 1 then 'CRÍTICO' when 2 then 'ALTO' when 3 then 'MÉDIO'
                                    when 4 then 'INFORMATIVO' end                  as severidade_evento,
    ev.vitimas_evento,
    ev.instalacao_evento,
    ev.sonda_evento,
    ev.poco_evento,
    ev.campo_evento,
    ev.bacia_evento,
    ev.municipio_evento,
    ev.estado_evento,
    ev.operadora_contrato_evento,
    ev.operadora_instalacao_evento
from normalizadas n
left join com_evento ce on ce.id_noticia = n.id_noticia
left join evento ev     on ev.chave_evento = ce.chave_evento
