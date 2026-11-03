"""Devolve à fila da IA as notícias que foram DESCARTADAS, para serem reclassificadas com o prompt/filtros novos.

Por que existe: o pipeline nunca reclassifica um título já gravado em raw.classificacoes_ia. Depois de mudar o
prompt ou o pré-filtro, as notícias descartadas pelas regras antigas (inclusive as marcadas como 'dedup')
continuariam fora da fila. Este script remove apenas as linhas relevante = false da janela informada;
elas voltam a ser candidatas na próxima execução do dbt (tag:pre_ia). As linhas relevante = true NÃO são tocadas.

Uso (a partir da raiz do projeto, com o .env carregado):
    python -m og_monitor.reprocessar --dias 7              # só mostra o que seria removido (simulação)
    python -m og_monitor.reprocessar --dias 7 --executar   # remove de fato
    python -m og_monitor.reprocessar --dias 7 --executar --so-dedup   # só as marcadas como duplicata
    python -m og_monitor.reprocessar --titulo-contem "afunda no mar com 115" --executar   # uma notícia específica
    python -m og_monitor.reprocessar --dias 30 --tudo --executar   # TUDO da janela, inclusive as aprovadas

Com --tudo as linhas aprovadas também voltam à fila e são reclassificadas do zero. Os alertas já enviados ficam em
raw.alertas_enviados e não se repetem; o raw.noticias (a coleta) não é tocado.
"""
import argparse
import logging

from psycopg2.extras import RealDictCursor

from og_monitor.db import get_conn

log = logging.getLogger(__name__)


def reprocessar(dias: int, executar: bool, so_dedup: bool, titulo_contem: str = "", tudo: bool = False) -> int:
    if titulo_contem:  # caso pontual: qualquer linha (aprovada ou não) cujo título contenha o trecho
        filtro = "titulo ILIKE %s"
        parametro = f"%{titulo_contem}%"
    elif tudo:
        filtro = "data_publicacao >= current_date - %s"
        parametro = dias
    else:
        filtro = "relevante = false AND data_publicacao >= current_date - %s"
        parametro = dias
        if so_dedup:
            filtro += " AND fonte_texto = 'dedup'"

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT coalesce(fonte_texto, '(sem fonte_texto)') AS fonte_texto, count(*) AS qtd
                FROM raw.classificacoes_ia
                WHERE {filtro}
                GROUP BY 1
                ORDER BY 2 DESC
                """,
                (parametro,),
            )
            resumo = cur.fetchall()
            total = sum(r["qtd"] for r in resumo)
            for r in resumo:
                log.info("   %-28s %5d", r["fonte_texto"], r["qtd"])

            if not executar:
                log.info("🔎 Simulação: %d notícia(s) dos últimos %d dias voltariam para a fila. "
                         "Use --executar para aplicar.", total, dias)
                return 0

            cur.execute(f"DELETE FROM raw.classificacoes_ia WHERE {filtro}", (parametro,))
            removidas = cur.rowcount
    log.info("♻️ %d notícia(s) devolvida(s) à fila. Rode o pipeline (ou dbt run --select tag:pre_ia) para reclassificar.",
             removidas)
    return removidas


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dias", type=int, default=7, help="janela por data_publicacao (padrão: 7, igual ao DIAS_RETROATIVOS)")
    ap.add_argument("--executar", action="store_true", help="aplica a remoção (sem isso, apenas simula)")
    ap.add_argument("--so-dedup", action="store_true", help="considera só as marcadas como duplicata por título")
    ap.add_argument("--tudo", action="store_true", help="devolve TODAS as notícias da janela, inclusive as aprovadas")
    ap.add_argument("--titulo-contem", default="",
                    help="caso pontual: remove (mesmo se aprovada) as linhas cujo título contém este trecho; ignora --dias")
    args = ap.parse_args()
    reprocessar(args.dias, args.executar, args.so_dedup, args.titulo_contem, args.tudo)


if __name__ == "__main__":
    main()