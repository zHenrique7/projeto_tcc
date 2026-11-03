"""Testa a leitura da matéria completa em algumas candidatas, sem chamar a IA (não gasta tokens da Groq).

Uso (raiz do projeto, venv ativo):
    python -m og_monitor.testar_scraper            # 5 candidatas
    python -m og_monitor.testar_scraper --n 10
    python -m og_monitor.testar_scraper --detalhes   # mostra o motivo de cada falha de leitura (HTTP 403, timeout...)
Mostra, para cada notícia, a URL real encontrada e como o texto foi obtido (newspaper4k, beautifulsoup_cloudflare
ou rss_feed = só a manchete) com o tamanho do texto.
"""
import argparse
import logging

from psycopg2.extras import RealDictCursor

from og_monitor.db import get_conn
from og_monitor.scraper import obter_texto, resolver_url


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=5, help="quantas candidatas testar (padrão: 5)")
    ap.add_argument("--detalhes", action="store_true", help="mostra também o motivo de cada tentativa que falhou")
    args = ap.parse_args()
    n = args.n
    logging.basicConfig(level=logging.INFO if args.detalhes else logging.WARNING, format="   ⚠️ %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT titulo, url_noticia, resumo_html FROM prata.prata_noticias_candidatas "
            "ORDER BY prioridade DESC, data_publicacao DESC LIMIT %s",
            (n,),
        )
        candidatas = cur.fetchall()

    leram = 0
    for i, row in enumerate(candidatas, 1):
        url = resolver_url(row["url_noticia"], row["resumo_html"])
        texto, fonte = obter_texto(url, row["resumo_html"])
        leram += int(fonte != "rss_feed")
        print(f"[{i}] {row['titulo'][:80]}\n    URL real : {url[:110]}\n    texto    : {fonte} ({len(texto)} caracteres)")
    print(f"\n{leram}/{len(candidatas)} com a matéria completa lida.")


if __name__ == "__main__":
    main()