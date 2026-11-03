"""Coleta de notícias (Google News + RSS) -> raw.noticias."""
import logging
import socket
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import feedparser
import yaml
from psycopg2.extras import execute_values

from og_monitor import config
from og_monitor.db import get_conn

log = logging.getLogger(__name__)

TZ_LOCAL = ZoneInfo("America/Sao_Paulo")
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
TIMEOUT_FEED_SEGUNDOS = 30  # feedparser usa urllib sem timeout: um feed travado seguraria a execução inteira
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _url_do_feed(feed: dict, dias: int) -> str:
    if feed["tipo"] == "google_news":
        consulta = f'{feed["consulta"]} when:{dias}d'
        return GOOGLE_NEWS_RSS.format(q=urllib.parse.quote_plus(consulta))
    return feed["url"]


def _data_publicacao(entry) -> datetime:
    """Converte a data do item para horário de Brasília (sem fuso), como no Power Query."""
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return datetime.now(TZ_LOCAL).replace(tzinfo=None, microsecond=0)
    return datetime(*t[:6], tzinfo=timezone.utc).astimezone(TZ_LOCAL).replace(tzinfo=None)


def coletar_noticias() -> int:
    """Lê todos os feeds de config/feeds.yml e grava as notícias novas em raw.noticias."""
    with open(config.FEEDS_PATH, encoding="utf-8") as f:
        feeds = yaml.safe_load(f)["feeds"]

    socket.setdefaulttimeout(TIMEOUT_FEED_SEGUNDOS)
    linhas = []
    vazios = []
    for feed in feeds:
        url = _url_do_feed(feed, config.DIAS_RETROATIVOS)
        parsed = feedparser.parse(url, agent=USER_AGENT)
        if parsed.bozo and not parsed.entries:
            log.warning("Feed '%s' falhou: %s", feed["nome"], parsed.get("bozo_exception"))
            continue
        for entry in parsed.entries:
            titulo = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not titulo or not link:
                continue
            fonte_href = (entry.get("source") or {}).get("href")
            linhas.append(
                (
                    _data_publicacao(entry),
                    feed["nome"],
                    titulo,
                    entry.get("summary", ""),
                    link,
                    fonte_href,
                )
            )
        log.info("Feed '%s': %d itens lidos", feed["nome"], len(parsed.entries))
        if not parsed.entries:
            vazios.append(feed["nome"])

    if vazios:
        log.warning("⚠️ Feeds sem nenhum item (consulta restritiva demais, bloqueio do Google ou feed fora do ar): %s",
                    ", ".join(vazios))
    if not linhas:
        log.warning("Nenhuma notícia coletada.")
        return 0

    with get_conn() as conn, conn.cursor() as cur:
        inseridas = execute_values(
            cur,
            """
            INSERT INTO raw.noticias
                (data_publicacao, fonte, titulo, resumo_html, url_noticia, url_fonte)
            VALUES %s
            ON CONFLICT (titulo, data_publicacao) DO NOTHING
            RETURNING titulo
            """,
            linhas,
            fetch=True,
        )
    log.info("📥 %d lidas, %d novas gravadas em raw.noticias", len(linhas), len(inseridas))
    return len(inseridas)
