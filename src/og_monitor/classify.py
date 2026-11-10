"""Etapa de IA: lê as candidatas (dbt) -> classifica com Groq -> grava em raw.classificacoes_ia.

Cada notícia é gravada logo após ser classificada: se a execução for interrompida, nada se perde
e o que já foi processado não volta para a IA (a próxima rodada do dbt exclui os títulos já gravados).
"""
import logging
import re
import time
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

from psycopg2.extras import RealDictCursor

from og_monitor import config
from og_monitor.classifier import ClassificationError, KeyPool, carregar_prompt, classificar_noticia
from og_monitor.db import get_conn
from og_monitor.scraper import obter_texto, resolver_url

log = logging.getLogger(__name__)


def _logger_execucao():
    """Dentro de uma execução do Prefect, devolve o logger da execução (as linhas aparecem na aba Logs do painel);
    fora dele (testes, linha de comando), o logger normal do módulo."""
    try:
        from prefect import get_run_logger

        return get_run_logger()
    except Exception:
        return log


def _texto_da_fonte(fonte_texto: str) -> str:
    return {"rss_feed": "só manchete/resumo do RSS (matéria não lida)",
            "newspaper4k": "matéria completa (newspaper4k)",
            "beautifulsoup_cloudflare": "matéria completa (BeautifulSoup/Cloudflare)"}.get(fonte_texto, fonte_texto)


def _bloco_log(i: int, total: int, row: dict, res: dict, url: str, fonte_texto: str) -> str:
    """Texto do log de uma notícia classificada: resultado, link, motivo e os campos extraídos."""
    marca = "✅ INCIDENTE" if res["relevante"] else "❌ descartada"
    linhas = [
        f"[{i:03d}/{total}] {marca}" + (f" | severidade {res['severidade']} | confiança {res['confianca']}" if res["relevante"] else ""),
        f"   Título:  {row['titulo']}",
        f"   Link:    {url}",
        f"   Feed:    {row['fonte']} | publicada em {row['data_publicacao']:%d/%m/%Y %H:%M}",
        f"   Texto:   {_texto_da_fonte(fonte_texto)}",
        f"   Motivo:  {res['motivo']}",
    ]
    if res["relevante"]:
        local = ", ".join(x for x in (res.get("municipio"), res.get("estado")) if x) or "não informado"
        ativo = " / ".join(x for x in (res.get("instalacao"), res.get("sonda"), res.get("poco"), res.get("campo")) if x) or "não informado"
        linhas += [
            f"   Evento:  {res.get('tipo_evento') or 'não informado'} | data do fato: {res.get('data_fato') or 'não informada'} | vítimas: {res.get('vitimas') if res.get('vitimas') is not None else 'não informado'}",
            f"   Ativo:   {ativo}",
            f"   Local:   {local}",
            f"   Operadora: {res.get('operadora_contrato') or res.get('operadora_instalacao') or 'não informada'}",
        ]
    return "\n".join(linhas)


def _celula(v) -> str:
    return str("" if v is None else v).replace("|", "/").replace("\n", " ")


def _publicar_tabela(registros: list, falhas: list, resumo: dict) -> None:
    """Cria na aba Artifacts da execução uma tabela com todas as notícias processadas (links clicáveis)."""
    try:
        from prefect.artifacts import create_markdown_artifact

        md = [
            "## Notícias processadas pela IA nesta execução",
            f"Candidatas: **{resumo['candidatas']}** | duplicadas: **{resumo['duplicadas']}** | classificadas: "
            f"**{resumo['classificadas']}** | incidentes: **{resumo['relevantes']}** | falhas: **{resumo['falhas']}**",
            "",
            "| # | Resultado | Severidade | Confiança | Título | Motivo | Evento | Ativo | Local | Vítimas | Data do fato | Texto | Feed |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in registros:
            md.append("| {n} | {res} | {sev} | {conf} | [{titulo}]({url}) | {motivo} | {tipo} | {ativo} | {local} | {vit} | {dfato} | {texto} | {feed} |".format(
                n=r["n"], res="✅ incidente" if r["relevante"] else "❌ descartada", sev=_celula(r["severidade"]),
                conf=_celula(r["confianca"]), titulo=_celula(r["titulo"])[:110], url=r["url"], motivo=_celula(r["motivo"]),
                tipo=_celula(r["tipo_evento"]), ativo=_celula(r["ativo"]), local=_celula(r["local"]), vit=_celula(r["vitimas"]),
                dfato=_celula(r["data_fato"]), texto=_celula(r["fonte_texto"]), feed=_celula(r["feed"])))
        if falhas:
            md += ["", "### Falhas", ""] + [f"- {_celula(t)[:110]}: {_celula(e)}" for t, e in falhas]
        create_markdown_artifact(key="noticias-classificadas", markdown="\n".join(md),
                                 description="Todas as notícias que a IA processou nesta execução")
    except Exception as e:  # o artefato é conveniência: nunca derruba a execução
        log.debug("Artefato do Prefect não criado: %s", e)

INSERT_SQL = """
INSERT INTO raw.classificacoes_ia
    (titulo, data_publicacao, url_noticia, fonte_texto, relevante, severidade, confianca, motivo, tipo_evento,
     sonda, instalacao, poco, campo, municipio, estado, operadora_contrato, operadora_instalacao,
     vitimas, data_fato)
VALUES
    (%(titulo)s, %(data_publicacao)s, %(url_noticia)s, %(fonte_texto)s, %(relevante)s, %(severidade)s,
     %(confianca)s, %(motivo)s, %(tipo_evento)s, %(sonda)s, %(instalacao)s, %(poco)s, %(campo)s, %(municipio)s,
     %(estado)s, %(operadora_contrato)s, %(operadora_instalacao)s, %(vitimas)s, %(data_fato)s)
ON CONFLICT (titulo, data_publicacao) DO NOTHING
"""

CAMPOS_VAZIOS = dict(
    severidade=None, confianca=None, tipo_evento=None, sonda=None, instalacao=None, poco=None, campo=None, municipio=None,
    estado=None, operadora_contrato=None, operadora_instalacao=None, vitimas=None, data_fato=None,
)


# Google News acrescenta o portal ao fim do título (" - Folha", " | G1"). Isso inflava a similaridade
# entre notícias diferentes do mesmo portal e escondia a duplicata real de portais diferentes.
_SUFIXO_PORTAL = re.compile(r"\s[-|–—]\s[^-|–—]{2,35}$")


def normalizar_titulo(titulo) -> str:
    t = _SUFIXO_PORTAL.sub("", str(titulo or ""))
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", t).split())


def similaridade(a, b) -> float:
    """Similaridade de títulos para detectar a MESMA notícia em portais diferentes.

    Títulos de acidente seguem moldes parecidos ("Trabalhador morre em acidente na plataforma P-52" x "... P-76"),
    então só a razão de caracteres confunde eventos distintos. Por isso, além da razão, exige-se que:
      - os números do título (P-52, P-76, 2 feridos...) sejam os mesmos, quando ambos os títulos têm números;
      - ao menos 60% das palavras sejam comuns (Jaccard).
    Se alguma condição falhar, o par não é tratado como duplicata (retorna 0.0).
    """
    na, nb = normalizar_titulo(a), normalizar_titulo(b)
    if not na or not nb:
        return 0.0
    nums_a, nums_b = set(re.findall(r"\d+", na)), set(re.findall(r"\d+", nb))
    if nums_a and nums_b and nums_a != nums_b:
        return 0.0
    ta, tb = set(na.split()), set(nb.split())
    if len(ta & tb) / len(ta | tb) < 0.6:
        return 0.0
    sm = SequenceMatcher(None, na, nb)
    if sm.real_quick_ratio() < 0.5 or sm.quick_ratio() < 0.5:  # cortes baratos antes do cálculo completo
        return 0.0
    return sm.ratio()


def _gravar(conn, registro: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(INSERT_SQL, registro)
    conn.commit()


def classificar_pendentes() -> dict:
    log = _logger_execucao()
    registros, lista_falhas = [], []
    pool = KeyPool(config.GROQ_API_KEYS)
    system_prompt = carregar_prompt()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT titulo, data_publicacao, fonte, url_noticia, resumo_html, prioridade
                FROM prata.prata_noticias_candidatas
                ORDER BY prioridade DESC, data_publicacao DESC
                """
            )
            candidatas = cur.fetchall()
            cur.execute(
                """
                SELECT titulo FROM raw.classificacoes_ia
                WHERE classificado_em >= now() - make_interval(days => %s)
                  AND fonte_texto IS DISTINCT FROM 'dedup'
                """,
                (config.DIAS_RETROATIVOS,),
            )
            recentes = [r["titulo"] for r in cur.fetchall()]

        log.info("📊 %d candidatas vindas do dbt (%d títulos já classificados na janela)", len(candidatas), len(recentes))

        # Deduplicação por similaridade de título (mesmo fato em portais diferentes)
        aceitas, referencias = [], list(recentes)
        for row in candidatas:
            if any(similaridade(row["titulo"], ref) > config.LIMIAR_SIMILARIDADE_TITULO for ref in referencias):
                _gravar(conn, {
                    **CAMPOS_VAZIOS, "titulo": row["titulo"], "data_publicacao": row["data_publicacao"],
                    "url_noticia": row["url_noticia"], "fonte_texto": "dedup", "relevante": False,
                    "motivo": "Duplicata de título (mesma notícia em outro portal).",
                })
                continue
            aceitas.append(row)
            referencias.append(row["titulo"])

        duplicadas = len(candidatas) - len(aceitas)
        pendentes = aceitas[: config.MAX_NOTICIAS_POR_EXECUCAO]
        # A SELEÇÃO é por prioridade (a cota da Groq vai para o que mais parece incidente), mas o PROCESSAMENTO é do mais
        # antigo para o mais novo: o dbt elege como notícia-raiz do evento a primeira classificada, e num backfill
        # (DIAS_RETROATIVOS alto) isso fazia uma matéria de opinião recente virar a raiz de um evento de meses atrás.
        pendentes.sort(key=lambda r: r["data_publicacao"])
        log.info("✂️ %d duplicadas por similaridade | 🤖 %d vão para a IA (limite %d)",
                 duplicadas, len(pendentes), config.MAX_NOTICIAS_POR_EXECUCAO)

        ok = falhas = relevantes = 0
        fontes_texto = Counter()  # como o texto foi obtido: newspaper4k, beautifulsoup_cloudflare ou rss_feed (só manchete)
        for i, row in enumerate(pendentes, 1):
            try:
                url_real = resolver_url(row["url_noticia"], row["resumo_html"])
                texto, fonte_texto = obter_texto(url_real, row["resumo_html"])
                res = classificar_noticia(
                    system_prompt, pool, row["titulo"], row["data_publicacao"], url_real, fonte_texto, texto
                )
                _gravar(conn, {
                    **res, "titulo": row["titulo"], "data_publicacao": row["data_publicacao"],
                    "url_noticia": url_real, "fonte_texto": fonte_texto,
                })
                ok += 1
                fontes_texto[fonte_texto] += 1
                relevantes += int(res["relevante"])
                log.info(_bloco_log(i, len(pendentes), row, res, url_real, fonte_texto))
                registros.append({
                    "n": i, "relevante": res["relevante"], "severidade": res["severidade"], "confianca": res["confianca"],
                    "titulo": row["titulo"], "url": url_real, "motivo": res["motivo"], "tipo_evento": res.get("tipo_evento"),
                    "ativo": " / ".join(x for x in (res.get("instalacao"), res.get("sonda"), res.get("poco"), res.get("campo")) if x),
                    "local": ", ".join(x for x in (res.get("municipio"), res.get("estado")) if x),
                    "vitimas": res.get("vitimas"), "data_fato": res.get("data_fato"), "fonte_texto": fonte_texto,
                    "feed": row["fonte"],
                })
            except ClassificationError as e:
                falhas += 1
                lista_falhas.append((row["titulo"], e))
                log.error("[%03d/%d] 🚨 FALHA | %s\n   Link: %s\n   Erro: %s", i, len(pendentes), row["titulo"], row["url_noticia"], e)
            time.sleep(config.GROQ_SLEEP_SECONDS)

    resumo = {"candidatas": len(candidatas), "duplicadas": duplicadas, "classificadas": ok,
              "relevantes": relevantes, "falhas": falhas, "fontes_texto": dict(fontes_texto)}
    log.info("📊 RESULTADO: %s", resumo)
    _publicar_tabela(registros, lista_falhas, resumo)
    if pendentes and falhas == len(pendentes):
        raise RuntimeError(f"Todas as {falhas} classificações falharam (ver logs: chaves Groq, cota ou rede).")
    return resumo